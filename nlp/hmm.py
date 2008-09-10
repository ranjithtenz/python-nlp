# Simple HMM implementation. Test code focuses on discrete signal reconstruction.

import sys
import random
from itertools import izip
from collections import defaultdict
import math

from countermap import CounterMap
from nlp import counter as Counter

class HiddenMarkovModel:
	# Distribution over next state given current state
	labels = list()
	transition = CounterMap()
	reverse_transition = CounterMap() # same as transitions but indexed in reverse (useful for decoding)

	# Distributions over mean & std. dev given state
	emission_mean = Counter()
	emission_stddev = Counter()
	emission_prob_funcs = dict()

	def train(self, labeled_sequence):
		label_counts = Counter()
		# Currently this assumes the HMM is multinomial
		last_label = None

		# Transitions
		for label, emission in labeled_sequence:
			label_counts[label] += 1.0
			self.emission_mean[label] += emission
			if last_label:
				self.transition[last_label][label] += 1.0
			else:
				self.transition["start"][label] += 1.0
			last_label = label

		self.transition.normalize()

		# Construct reverse transition probabilities
		for label, counter in self.transition.iteritems():
			for sublabel, score in counter.iteritems():
				self.reverse_transition[sublabel][label] = score

		# Emissions
		for label in self.emission_mean:
			self.emission_mean[label] /= label_counts[label]

		for label, emission in labeled_sequence:
			if (label_counts[label] > 1):
				# Unbiased sample variance (sqrt taken later to convert to std dev)
				self.emission_stddev[label] += (emission - self.emission_mean[label])**2 / (label_counts[label] - 1)

		for label in self.emission_stddev:
			self.emission_stddev[label] = self.emission_stddev[label] ** (0.5)

		self.labels = self.emission_stddev.keys()

		std_dev_coefficient = math.sqrt(2.0 * math.pi)
		for label in self.labels:
			self.emission_prob_funcs[label] = lambda x: 1 / (self.emission_stddev[label] * std_dev_coefficient) * \
				math.exp(- (x - self.emission_mean[label])**2 / (2 * self.emission_stddev[label]**2))

	def __get_emission_probs(self, emission):
		# return a Counter distribution over labels given the emission
		emission_prob = Counter()

		for label in self.labels:
			emission_prob[label] = self.emission_prob_funcs[label](emission)

		return emission_prob

	def label(self, emission_sequence):
		# This needs to perform viterbi decoding on the the emission sequence

		# Backtracking pointers - backtrack[position] = {state : prev, ...}
		backtrack = [defaultdict(lambda: None) for state in emission_sequence]

		# Scores are indexed by pos + 1 (so we can initialize it with uniform probability, or the stationary if we have it)
		scores = [Counter() for state in xrange(len(emission_sequence)+1)]
		for label in self.labels: scores[0][label] += 1.0
		scores[0].normalize()

		for pos, emission in enumerate(emission_sequence):
			# At each position calculate the transition scores and the emission probabilities (independent given the state!)
			emission_probs = self.__get_emission_probs(emission)
			transition_probs = CounterMap()

			# scores[pos+1] = max(scores[pos][label] * transitions[label][nextlabel] for label, nextlabel)
			# backtrack = argmax(^^)
			for label in self.labels:
				transition_scores = scores[pos] * self.reverse_transition[label]
				scores[pos+1][label] = max(transition_scores.itervalues())
				backtrack[pos][label] = transition_scores.arg_max()

		# Now decode
		states = list()
		current = scores[-1].arg_max()
		print "last state: %s" % current
		for pos in xrange(len(backtrack)-1, 0, -1):
			states.append(current)
			current = backtrack[pos][current]

		states.reverse()
		return states

	def __sample_transition(self, label):
		sample = random.sample()

		for next, prob in self.transition[label].iteritems():
			sample -= prob
			if sample <= 0.0: return next

		assert False, "Should have returned a next state"

	def __sample_emission(self, label):
		return random.gauss(self.emission_mean[label], self.emission_stddev[label])

	def sample(self, start=None):
		"""Returns a generator yielding a sequence of (state, emission) pairs
		generated by the modeled sequence"""
		state = start
		if not state:
			state = random.choice(self.transition.keys())
			for i in xrange(1000): state = self.__sample_transition(state)

		while True:
			yield (state, self.__sample_emission(state))
			state = self.__sample_transition(state)

def toy_problem(args):
	# Simulate a 3 state markov chain with transition matrix (given states in row vector):
	#  (destination)
	#   1    2    3
	# 1 0.7  0.3  0
	# 2 0.05 0.4  0.55
	# 3 0.25 0.25 0.5
	transitions = CounterMap()

	transitions['1']['1'] = 0.7
	transitions['1']['2'] = 0.3
	transitions['1']['3'] = 0.0

	transitions['2']['1'] = 0.05
	transitions['2']['2'] = 0.4
	transitions['2']['3'] = 0.55

	transitions['3']['1'] = 0.25
	transitions['3']['2'] = 0.25
	transitions['3']['3'] = 0.5

	def sample_transition(label):
		sample = random.random()

		for next, prob in transitions[label].iteritems():
			sample -= prob
			if sample <= 0.0: return next

		assert False, "Should have returned a next state"

	# And gaussian emissions (state, (mean, std dev)): {1 : (0.5, 1), 2 : (0.75, 0.1), 3 : (0.4, 0.3)}
	emissions = {'1' : (0.5, 1), '2' : (0.75, 0.1), '3' : (0.4, 0.3)}

	def sample_emission(label):
		return random.gauss(*emissions[label])
	
	# Create the training/test data
	states = ['1', '2', '3']
	start = random.choice(states)

	# Burn-in (easier than hand-calculating stationary distribution & sampling)
	for i in xrange(10000):	start = sample_transition(start)

	def label_generator(start_label):
		next = start_label
		while True:
			yield next
			next = sample_transition(next)

	training_labels = [val for _, val in izip(xrange(10000), label_generator(start))]
	training_emissions = [sample_emission(label) for label in training_labels]
	training_signal = zip(training_labels, training_emissions)

	# Training phase
	signal_decoder = HiddenMarkovModel()
	signal_decoder.train(training_signal)

	# Labeling phase: given a set of emissions, guess the correct states
	start = random.choice(states)
	for i in xrange(10000):	start = sample_transition(start)
	test_labels = [val for _, val in izip(xrange(500), label_generator(start))]
	test_emissions = [sample_emission(label) for label in training_labels]

	guessed_labels = signal_decoder.label(test_emissions)
	correct = sum(1 for guessed, correct in izip(guessed_labels, test_labels) if guessed == correct)

	print "%d labels recovered correctly (%.2f%% correct out of %d)" % (correct, float(correct) / float(len(test_labels)), len(test_labels))

if __name__ == "__main__":
	toy_problem(sys.argv)