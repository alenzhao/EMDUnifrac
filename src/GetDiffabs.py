# This script will take as input two files, one with a list of profiles, one with associated metadata (one per line)
# both in the same order, and then will group according to the metadata and find the most significant diffab entries,
# i.e. the tax_path_sn's that contribute most the the unifrac distance
# USER BE AWARE THAT YOU SHOULD NOT TRUST RESULTS THAT HAVE MISSING TAXONOMIC RANKS!!! Mostly a MetaPhlAn2 problem

# TO DO:
# 1. add a "top k" parameter (mutually exclusive to the threshold) that gives the top k number of diffab organisms
# 2. currently this is quite inefficient as I'm looping over the files multiple times (and saving ALL the tax_ids to names) etc

# NEED TO FIX THE FACT THAT THE exported data matrix is not doing things at a fixed rank...

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
	arg('--meta', metavar='metadata_file', required=True, default=None, type=str,
					help="File with the metadata associated to input file (in the same order!)")
	arg('--threshold', metavar='significant_threshold', required=False, default=2, type=float,
					help="Threshold for significance: 1 = one standard deviation away, 0 = include everything,"
					" negative = only get most over-expressed")
	arg('--rank', metavar='taxonomic_rank', required=False, default=None, type=str,
					help='optional argument, rank is one of {superkingdom, phylum, class, order, family, genus, species}'
					' to restrict yourself to consider only those differentially expressed organisms at that rank.'
					' Default is to include all ranks')
	arg('--output', metavar='output', required=True, default=None, type=str,
					help='output txt file for results')
	arg('--outputdata', metavar='output data file', required=False, default=None, type=str,
					help='tsv file for output of extracted abundance data')
	arg('--filter', metavar='filter value', required=False, default=None, type=float,
					help='filter value to use before finding differentially abundant organisms. Outputdata file will'
					'still contain the raw, normalized values though.')
	return vars(parser.parse_args())


def get_differentially_expressed_critters(
		file_names_file, meta_data_file, significant_threshold,
		rank, output_file, extracted_abundances_file_name, filter_value):
	rank_length = None
	if rank == "superkingdom":
		rank_length = 1
	elif rank == "phylum":
		rank_length = 2
	elif rank == "class":
		rank_length = 3
	elif rank == "order":
		rank_length = 4
	elif rank == "family":
		rank_length = 5
	elif rank == "genus":
		rank_length = 6
	elif rank == "species":
		rank_length = 7
	elif rank == "strain":
		rank_length = 8


	meta_data = []
	meta_data_unique = set()
	fid = open(meta_data_file, 'r')
	for line in fid.readlines():
		data = line.strip()
		meta_data.append(data)
		meta_data_unique.add(data)
	fid.close()

	file_names = []
	fid = open(file_names_file, 'r')
	for line in fid.readlines():
		file_name = line.strip()
		file_names.append(file_name)
	fid.close()

	if len(file_names) != len(meta_data):
		print('Ack! Your metadata file and files names file have a different number of elements!')
		raise Exception

	meta_data_unique = sorted(list(meta_data_unique))  # get the unique metadata items
	file_names_grouped = [list() for item in meta_data_unique]  # initialize the groupings with empty sets
	for data_index in xrange(len(meta_data)):
		data = meta_data[data_index]
		group_index = meta_data_unique.index(data)
		file_names_grouped[group_index].append(file_names[data_index])

	grouped_profiles = []
	significant_tax_ids_to_names = dict()
	for group_index in xrange(len(file_names_grouped)):
		profile_grouped = None  # Initial profile is empty
		for file_name in file_names_grouped[group_index]:
			if not os.path.exists(file_name):
				print('Watch out, this file does not exist and will not be used in the following calculation: %s' % file_name)
				pass
			else:
				profile = PF.Profile(file_name)
				print('First processing of file %s' % file_name)
			# Normalize first, just in case one of the profiles was highly sampled and this was not taken into account
			profile.normalize()
			# If requested, filter the profile first
			if filter_value:
				profile.threshold(filter_value)  # filter
				profile.normalize()  # then normalize again
			# Get ALL the tax_id -> name mappings
			for key in profile._data.keys():
				if "tax_path_sn" in profile._data[key]:
					if len(profile._data[key]["tax_path_sn"]) >= 1:
						significant_tax_ids_to_names[key] = profile._data[key]["tax_path_sn"][-1]
			if not profile_grouped:
				profile_grouped = profile
			else:  #otherwise, merge it
				profile_grouped.merge(profile)
		# After grouping, normalize it
		profile_grouped.normalize()
		# And add it to the grouped profiles
		grouped_profiles.append(profile_grouped)

	print('Files loaded, now running unifrac')
	# Now do EMDUnifrac and find over/under-expression
	# over/under will be a dictionary with keys as the metadatas, values as tax path, tax path sn, or amount
	over_under_tax_path = dict()
	over_under_tax_path_sn = dict()
	over_under_amount = dict()
	for i in xrange(len(grouped_profiles)):
		for j in xrange(i + 1, len(grouped_profiles)):
			profile1 = grouped_profiles[i]
			meta_data1 = meta_data_unique[i]
			profile2 = grouped_profiles[j]
			meta_data2 = meta_data_unique[j]
			(Tint, lint, nodes_in_order, nodes_to_index, prob1, prob2) = profile1.make_unifrac_input_and_normalize(profile2)
			(Z, diffab) = EMDU.EMDUnifrac_weighted(Tint, lint, nodes_in_order, prob1, prob2)
			diffab_keys = diffab.keys()
			diffab_vals = diffab.values()
			mean = np.mean(np.abs(diffab_vals))  # get the mean
			std = np.std(np.abs(diffab_vals))  # and the standard deviation
			significant_tax_ids = []
			significant_values = []
			index_to_nodes = dict(zip(nodes_to_index.values(), nodes_to_index.keys()))
			max_ind = np.argmax(diffab_vals)  # Index of the maximially expressed tax_id
			if significant_threshold >= 0:  # If threshold is positive, use as factor for std_dev
				for diff_ab_ind in xrange(len(diffab_vals)):
					val = diffab_vals[diff_ab_ind]
					if abs(val) >= mean + significant_threshold * std:  # if the abs(val) exceeds threshold of the std dev
						index = diffab_keys[diff_ab_ind][0]  # find the index and add it to the significant ones
						tax_id = index_to_nodes[index]
						significant_tax_ids.append(tax_id)
						significant_values.append(val)
			elif significant_threshold < 0:  # Otherwise, just pick off the biggest (most over-expressed)
					index = max_ind
					tax_id = index_to_nodes[index]
					val = diffab_vals[index]
					significant_tax_ids.append(tax_id)
					significant_values.append(val)


			# Pull off the significant tax paths and tax path names
			significant_tax_path_sns = []
			significant_tax_paths = []
			for key in significant_tax_ids:
				if key in profile1._data:
					if rank_length:  # if rank length has been specified, only output stuff at this rank
						path_length = len(profile1._data[key]["tax_path"])  # get path length
						if path_length == rank_length:  # check if it is correct
							tax_path = "|".join(profile1._data[key]["tax_path"])  # populate
							significant_tax_paths.append(tax_path)
							tax_path_sn = "|".join(profile1._data[key]["tax_path_sn"])
							significant_tax_path_sns.append(tax_path_sn)
					else:
						tax_path = "|".join(profile1._data[key]["tax_path"])
						significant_tax_paths.append(tax_path)
						tax_path_sn = "|".join(profile1._data[key]["tax_path_sn"])
						significant_tax_path_sns.append(tax_path_sn)
				elif key in profile2._data:
					if rank_length:  # if rank length has been specified, only output stuff at this rank
						path_length = len(profile2._data[key]["tax_path"])  # get path length
						if path_length == rank_length:  # check if it is correct
							tax_path = "|".join(profile2._data[key]["tax_path"])  # populate
							significant_tax_paths.append(tax_path)
							tax_path_sn = "|".join(profile2._data[key]["tax_path_sn"])
							significant_tax_path_sns.append(tax_path_sn)
					else:
						tax_path = "|".join(profile2._data[key]["tax_path"])
						significant_tax_paths.append(tax_path)
						tax_path_sn = "|".join(profile2._data[key]["tax_path_sn"])
						significant_tax_path_sns.append(tax_path_sn)
			over_under_amount[meta_data_unique[i], meta_data_unique[j]] = significant_values
			over_under_tax_path[meta_data_unique[i], meta_data_unique[j]] = significant_tax_paths
			over_under_tax_path_sn[meta_data_unique[i], meta_data_unique[j]] = significant_tax_path_sns

	print('writing output to file')
	# Now I just have to figure out a reasonable way to export this stuff... I hope I can do it in a flat file of some sort
	# Let's just make it a flat text file
	fid = open(output_file, 'w')
	for i in xrange(len(grouped_profiles)):
		for j in xrange(i + 1, len(grouped_profiles)):
			significant_values_raw = over_under_amount[meta_data_unique[i], meta_data_unique[j]]
			significant_tax_paths_raw = over_under_tax_path[meta_data_unique[i], meta_data_unique[j]]
			significant_tax_path_sns_raw = over_under_tax_path_sn[meta_data_unique[i], meta_data_unique[j]]
			# sort by the tax_path lengths
			lengths = [len(item.split("|")) for item in significant_tax_paths_raw]
			significant_values = [x for (y, x) in sorted(zip(lengths, significant_values_raw))]
			significant_tax_paths = [x for (y, x) in sorted(zip(lengths, significant_tax_paths_raw))]
			significant_tax_path_sns = [x for (y, x) in sorted(zip(lengths, significant_tax_path_sns_raw))]
			for write_index in xrange(len(significant_values)):
				val = significant_values[write_index]
				path = significant_tax_paths[write_index]
				sn = significant_tax_path_sns[write_index]
				# Add a helpful last column
				if val <= 0:
					fid.write("%s,%s\t%s\t%s\t%f\tunder-expressed in %s\n" % (
						meta_data_unique[i], meta_data_unique[j], path, sn, val, meta_data_unique[i]))
				else:
					fid.write("%s,%s\t%s\t%s\t%f\tover-expressed in %s\n" % (
						meta_data_unique[i], meta_data_unique[j], path, sn, val, meta_data_unique[i]))

	fid.close()
	# Done!
	# Negative means under-expressed in profile1, positive means over-expressed in profile2

	# Now let's extract these significant taxid's from each of the data sets and write to file
	# row = organism
	# column = metadata name
	print('pulling off data')
	# get all profiles up front
	profiles = []
	for file_name_index in xrange(len(file_names)):
		file_name = file_names[file_name_index]
		print('getting file %s' % file_name)
		profile = PF.profile(file_name)
		profile.normalize()
		profiles.append(profile)
	significant_tax_ids = [item.split("|")[-1] for sublist in over_under_tax_path.values() for item in sublist]  # flatten the list
	if extracted_abundances_file_name is not None:
		if len(significant_tax_ids) > 0:  # if there's anything to work with
			unique_significant_tax_ids = list(set(significant_tax_ids))
			fid = open(extracted_abundances_file_name, 'w')
			fid.write('name/metadata\t')
			for name_index in xrange(len(meta_data) - 1):  # meta-data as columns
				fid.write('%s\t' % meta_data[name_index])
			fid.write('%s\n' % meta_data[-1])  # last one is a new-line
			for tax_id in unique_significant_tax_ids:  # over each of the significant tax_ids
				fid.write('%s\t' % significant_tax_ids_to_names[tax_id])  # label the row
				for file_name_index in xrange(len(file_names) - 1):  # loop through the profiles
					#file_name = file_names[file_name_index]
					#profile = PF.Profile(file_name)  # import
					#print('Importing file %s' % file_name)
					#profile.normalize()  # normalize
					profile = profiles[file_name_index]
					if tax_id in profile._data:  # if it's in there, write the abundance, if not, put a zero
						fid.write('%f\t' % profile._data[tax_id]["abundance"])
					else:
						fid.write('0\t')
				# Make the last line not end in tab
				#profile = PF.Profile(file_names[-1])  # import
				#profile.normalize()  # normalize
				profile = profiles[-1]
				if tax_id in profile._data:  # if it's in there, write the abundance, if not, put a zero
					fid.write('%f' % profile._data[tax_id]["abundance"])
				else:
					fid.write('0')
				fid.write('\n')  # start new line
			fid.close()  # close the file
		else:
			print("No significant tax IDS, not saving data matrix")


if __name__ == '__main__':
	par = read_params(sys.argv)
	get_differentially_expressed_critters(
		par['input'], par['meta'], par['threshold'],
		par['rank'], par['output'], par['outputdata'], par['filter'])




#file_names_file = '../data/FileNames.txt'
#meta_data_file = '../data/metadata.txt'
#significant_threshold = -2  # this means two standard deviations, negative value means the most over-expressed, 0 value means everything
#rank = ""  # Only perform this test at the given rank
#output_file = '../data/testout.txt'
