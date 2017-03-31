# This is an example file of how to use the CAMI parser in parallel
# First, do it in serial to see if it works... seems fast enough!
import EMDUnifrac as EMDU
import numpy as np
import argparse
import sys
import os
# Get the CAMIProfiling tools package, since that contains the parser etc.
sys.path.append('/home/dkoslicki/Dropbox/Repositories/CAMIProfilingTools/src')
sys.path.append('/nfs1/Koslicki_Lab/koslickd/Repositories/CAMIProfilingTools/src')
import ProfilingTools as PF

__author__ = 'David Koslicki (dmkoslicki@gmail.com, david.koslicki@math.oregonstate.edu)'
__version__ = '1.0.0'
__date__ = '28 Mar 2017'


def read_params(args):
	parser = argparse.ArgumentParser(description='')
	arg = parser.add_argument
	arg('--input', metavar='files_file', type=str, required=True,
		default=None, help="File of CAMI profile files to use")
	arg('--output', metavar='output_file', required=True, default=None, type=str,
		help="Output file (you should have this end in .csv as it is a matrix)")
	return vars(parser.parse_args())


def make_dist_mat(files_file, output):
	files = []
	fid = open(files_file, 'r')
	for line in fid.readlines():
		files.append(line.strip())

	fid.close()

	D = np.zeros((len(files), len(files)))
	profiles = []
	for i in xrange(len(files)):
		profiles.append(PF.Profile(files[i]))

	for i in xrange(len(files)):
		for j in xrange(i+1, len(files)):
			print("on pair (%d,%d)" % (i, j))
			in_file_1 = files[i]
			in_file_2 = files[j]
			if os.path.exists(in_file_1) and os.path.exists(in_file_2):
				profile1 = profiles[i]
				profile2 = profiles[j]
				(Tint, lint, nodes_in_order, nodes_to_index, prob1, prob2) = profile1.make_unifrac_input_and_normalize(profile2)
				(Z, F, diffab) = EMDU.EMDUnifrac_weighted_flow(Tint, lint, nodes_in_order, prob1, prob2)
				#(Z, diffab) = EMDU.EMDUnifrac_weighted(Tint, lint, nodes_in_order, prob1, prob2)
				D[i, j] = Z
				D[j, i] = Z
	np.savetxt(output, D, delimiter=',', newline='\n')

if __name__ == '__main__':
	par = read_params(sys.argv)
	make_dist_mat(par['input'], par['output'])
