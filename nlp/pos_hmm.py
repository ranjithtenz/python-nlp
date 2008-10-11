from itertools import islice, izip
import sys
from time import time

from hmm import HiddenMarkovModel, START_LABEL, STOP_LABEL
from penntreebankreader import PennTreebankReader

def merge_stream(stream):
	# Combine sentences into one long string, with each sentence start with <START> and ending with <STOP>
	# [1:-2] cuts the leading STOP_LABEL and the trailing START_LABEL
	sentences = []
	tag_stream = []
	for tags, sentence in stream:
		sentences.append(START_LABEL)
		tag_stream.append(START_LABEL)
		for word in sentence:
			sentences.append(word)
		for tag in tags:
			tag_stream.append(tag)
		sentences.append(STOP_LABEL)
		tag_stream.append(STOP_LABEL)

	return zip(tag_stream, sentences)

def pos_problem(args):
	dataset_size = None
	if len(args) > 0: dataset_size = int(args[0])
	# Load the dataset
	print "Loading dataset"
	start = time()
	if dataset_size: tagged_sentences = list(islice(PennTreebankReader.read_pos_tags_from_directory("data/wsj"), dataset_size))
	else: tagged_sentences = list(PennTreebankReader.read_pos_tags_from_directory("data/wsj"))
	stop = time()
	print "Reading: %f" % (stop-start)

	print "Creating streams"
	start = time()
	training_sentences = tagged_sentences[0:len(tagged_sentences)*4/5]
	validation_sentences = tagged_sentences[len(tagged_sentences)*8/10+1:len(tagged_sentences)*9/10]
	testing_sentences = tagged_sentences[len(tagged_sentences)*9/10+1:]
	print "Training: %d" % len(training_sentences)
	print "Validation: %d" % len(validation_sentences)
	print "Testing: %d" % len(testing_sentences)

	print testing_sentences
	
	training_stream, validation_stream = map(merge_stream, (training_sentences, validation_sentences))
	stop = time()
	print "Streaming: %f" % (stop-start)

	print "Training"
	start = time()
	pos_tagger = HiddenMarkovModel()
	pos_tagger.train(training_stream[1:-2])
	stop = time()
	print "Training: %f" % (stop-start)

	print "Testing"
	start = time()

	for correct_labels, emissions in testing_sentences:
		guessed_labels = pos_tagger.label(emissions, debug=False)
		num_correct = 0
		for correct, guessed in izip(correct_labels, guessed_labels):
			if correct == START_LABEL or correct == STOP_LABEL: continue
			if correct == guessed: num_correct += 1

		if correct_labels != guessed_labels:
			guessed_score = pos_tagger.score(zip(guessed_labels, emissions))
			correct_score = pos_tagger.score(zip(correct_labels, emissions))

			print "Guessed: %f, Correct: %f" % (guessed_score, correct_score)

			debug_label = lambda: pos_tagger.label(emissions, debug=True)#start_at=20)
			assert guessed_score >= correct_score, "Decoder sub-optimality (%f for guess, %f for correct), %s" % (guessed_score, correct_score, debug_label())

	stop = time()
	print "Testing: %f" % (stop-start)

	print "%d correct (%.3f%% of %d)" % (num_correct, 100.0 * float(num_correct) / float(len(correct_labels)), len(correct_labels))

if __name__ == "__main__":
	pos_problem(sys.argv[1:])