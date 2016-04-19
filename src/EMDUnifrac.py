import math,string,fpformat,random,re,sys,subprocess,getopt  # import of standard modules
import numpy as np
import dendropy

#print("WARNING: all branch lengths must be non-zero")
#print("WARNING: development still in progress. Use at your own risk")



def simulate_data(basis):
	'''
	Simulate environments, suitable for feeding directly to FastUnifrac. 
	Input is a list of nodes on which the distribution will be given.
	Will return distribution only on labeled nodes. Returns (envs)
	'''
	weights_sample1 = np.random.exponential(scale=1.0, size=(1,len(basis))).transpose()
	#Multiply since fast_unifrac expects numbers > 1
	weights_sample1 = 1000*weights_sample1 
	weights_sample2 = np.random.exponential(scale=1.0, size=(1,len(basis))).transpose()
	#make it sparse
	weights_sample2 = 1000*weights_sample2
	envs = dict()
	i=0
	for node in basis:
		envs[node] = {'sample1':weights_sample1[i],'sample2':weights_sample2[i]}
		i = i+1
	return (envs)


def parse_tree(tree_str):
	'''
	(Tint,lint,nodes_in_order) = parse_tree(tree_str) 
	This function will parse a newick tree string and return the dictionary of ancestors Tint.
	Tint indexes the nodes by integers, Tint[i] = j means j is the ancestor of i.
	lint is a dictionary returning branch lengths: lint[i,j] = w(i,j) the weight of the edge connecting i and j.
	nodes_in_order is a list of the nodes in the input tree_str such that T[i]=j means nodes_in_order[j] is an ancestor
	of nodes_in_order[i]. Nodes are labeled from the leaves up.
	'''
	dtree = dendropy.Tree.get(data=tree_str, schema="newick", suppress_internal_node_taxa=False,store_tree_weights=True)
	#Name all the internal nodes
	nodes = dtree.nodes()
	i=0
	for node in nodes:
		if node.taxon == None:
			node.taxon = dendropy.datamodel.taxonmodel.Taxon(label="temp"+str(i))
			i = i+1
	full_nodes_in_order = [item for item in dtree.levelorder_node_iter()]  # i in path from root to j only if i>j
	full_nodes_in_order.reverse()
	nodes_in_order = [item.taxon.label for item in full_nodes_in_order]  # i in path from root to j only if i>j
	Tint = dict()
	lint = dict()
	nodes_to_index = dict(zip(nodes_in_order, range(len(nodes_in_order))))
	for i in range(len(nodes_in_order)):
		node = full_nodes_in_order[i]
		parent = node.parent_node
		if parent != None:
			Tint[i] = nodes_to_index[parent.taxon.label]
			lint[nodes_to_index[node.taxon.label], nodes_to_index[parent.taxon.label]] = node.edge.length
	return (Tint,lint,nodes_in_order)



def parse_tree_file(tree_str_file):
	'''
	(Tint,lint,nodes_in_order) = parse_tree(tree_str_file) 
	This function will parse a newick tree file (in the file given by tree_str_file) and return the dictionary of ancestors Tint.
	Tint indexes the nodes by integers, Tint[i] = j means j is the ancestor of i.
	lint is a dictionary returning branch lengths: lint[i,j] = w(i,j) the weight of the edge connecting i and j.
	nodes_in_order is a list of the nodes in the input tree_str such that T[i]=j means nodes_in_order[j] is an ancestor
	of nodes_in_order[i]. Nodes are labeled from the leaves up.
	'''
	dtree = dendropy.Tree.get(path = tree_str_file, schema="newick", suppress_internal_node_taxa=False,store_tree_weights=True)
	#Name all the internal nodes
	nodes = dtree.nodes()
	i=0
	for node in nodes:
		if node.taxon == None:
			node.taxon = dendropy.datamodel.taxonmodel.Taxon(label="temp"+str(i))
			i = i+1
	full_nodes_in_order = [item for item in dtree.levelorder_node_iter()]  # i in path from root to j only if i>j
	full_nodes_in_order.reverse()
	nodes_in_order = [item.taxon.label for item in full_nodes_in_order]  # i in path from root to j only if i>j
	Tint = dict()
	lint = dict()
	nodes_to_index = dict(zip(nodes_in_order, range(len(nodes_in_order))))
	for i in range(len(nodes_in_order)):
		node = full_nodes_in_order[i]
		parent = node.parent_node
		if parent != None:
			Tint[i] = nodes_to_index[parent.taxon.label]
			lint[nodes_to_index[node.taxon.label], nodes_to_index[parent.taxon.label]] = node.edge.length
	return (Tint,lint,nodes_in_order)

def parse_envs(envs, nodes_in_order):
	'''
	(envs_prob_dict, samples) = parse_envs(envs, nodes_in_order)
	This function takes an environment envs and the list of nodes nodes_in_order and will return a dictionary envs_prob_dict
	with keys given by samples. envs_prob_dict[samples[i]] is a probability vector on the basis nodes_in_order denoting for sample i.
	'''
	nodes_in_order_dict = dict(zip(nodes_in_order,range(len(nodes_in_order))))
	for node in envs.keys():
		if node not in nodes_in_order_dict:
			print("Warning: environments contain taxa " + node + " not present in given taxonomic tree. Ignoring")
	envs_prob_dict = dict()
	for i in range(len(nodes_in_order)):
		node = nodes_in_order[i]
		if node in envs:
			samples = envs[node].keys()
			for sample in samples:
				if sample not in envs_prob_dict:
					envs_prob_dict[sample] = np.zeros(len(nodes_in_order))
					envs_prob_dict[sample][i] = envs[node][sample]
				else:
					envs_prob_dict[sample][i] = envs[node][sample]
	#Normalize samples
	samples = envs_prob_dict.keys()
	for sample in samples:
		envs_prob_dict[sample] = envs_prob_dict[sample]/envs_prob_dict[sample].sum()
	return (envs_prob_dict, samples)




def EMDUnifrac_weighted_flow(Tint, lint, nodes_in_order, P, Q):
	'''
	(Z, F) = EMDUnifrac_weighted_flow(Tint, lint, nodes_in_order, P, Q)
	This function takes the ancestor dictionary Tint, the lengths dictionary lint, the basis nodes_in_order
	and two probability vectors P and Q (typically P = envs_prob_dict[samples[i]], Q = envs_prob_dict[samples[j]]).
	Returns the weighted Unifrac distance Z and the flow F. The flow F is a dictionary with keys of the form (i,j) where
	F[(i,j)] == num means that in the calculation of the Unifrac distance, a total mass of num was moved from the node
	nodes_in_order[i] to the node nodes_in_order[j].
	'''
	num_nodes = len(nodes_in_order)
	F = dict()
	G = dict()
	Z = 0
	w = np.zeros(num_nodes)
	pos = dict()
	neg = dict()
	for i in range(num_nodes):
		pos[i] = set([])
		neg[i] = set([])
	for i in range(num_nodes):
		if P[i]>0 and Q[i]>0:
			F[(i,i)] = np.minimum(P[i],Q[i])
		G[(i,i)] = P[i] - Q[i]
		if P[i] > Q[i]:
			pos[i].add(i)
		elif P[i] < Q[i]:
			neg[i].add(i)
		posremove = set()
		negremove = set()
		for j in pos[i]:
			for k in neg[i]:
				if (j not in posremove) and (k not in negremove):
					val = np.minimum(G[(i,j)], -G[(i,k)])
					if val > 0:
						F[(j,k)] = np.minimum(G[(i,j)], -G[(i,k)])
						G[(i,j)] = G[(i,j)] - val
						G[(i,k)] = G[(i,k)] + val
						Z = Z + (w[j] + w[k])*val
					if G[(i,j)] == 0:
						posremove.add(j)
					if G[(i,k)] == 0:
						negremove.add(k)
		pos[i].difference_update(posremove)
		neg[i].difference_update(negremove)
		if i < num_nodes-1:
			for j in pos[i].union(neg[i]):
					if (Tint[i],j) in G:
						G[(Tint[i],j)] = G[(Tint[i],j)] + G[(i,j)]
					else:
						G[(Tint[i],j)] = G[(i,j)]
					w[j] = w[j] + lint[i,Tint[i]]
			pos[Tint[i]] |= pos[i]
			neg[Tint[i]] |= neg[i]
	return (Z, F)  # The returned flow is on the basis nodes_in_order and is given in sparse matrix dictionary format. eg {(0,0):.5,(1,2):.5}


#This will return the EMDUnifrac distance only
def EMDUnifrac_weighted(Tint, lint, nodes_in_order, P, Q):
	'''
	Z = EMDUnifrac_weighted(Tint, lint, nodes_in_order, P, Q)
	This function takes the ancestor dictionary Tint, the lengths dictionary lint, the basis nodes_in_order
	and two probability vectors P and Q (typically P = envs_prob_dict[samples[i]], Q = envs_prob_dict[samples[j]]).
	Returns the weighted Unifrac distance Z and the flow F. The flow F is a dictionary with keys of the form (i,j) where
	F[(i,j)] == num means that in the calculation of the Unifrac distance, a total mass of num was moved from the node
	nodes_in_order[i] to the node nodes_in_order[j].
	'''
	num_nodes = len(nodes_in_order)
	Z = 0
	partial_sums = P - Q
	for i in range(num_nodes - 1):
		val = partial_sums[i]
		partial_sums[Tint[i]] += val
		Z += lint[i, Tint[i]]*abs(val)
	return Z


#This will return the EMDUnifrac distance only
def EMDUnifrac_unweighted(Tint, lint, nodes_in_order, P, Q):
	'''
	Z = EMDUnifrac_unweighted(Tint, lint, nodes_in_order, P, Q)
	This function takes the ancestor dictionary Tint, the lengths dictionary lint, the basis nodes_in_order
	and two probability vectors P and Q (typically P = envs_prob_dict[samples[i]], Q = envs_prob_dict[samples[j]]).
	Returns the unweighted Unifrac distance Z and the flow F. The flow F is a dictionary with keys of the form (i,j) where
	F[(i,j)] == 1 means that in the calculation of the Unifrac distance, a total mass of 1 was moved from the node
	nodes_in_order[i] to the node nodes_in_order[j].
	'''
	num_nodes = len(nodes_in_order)
	Z = 0
	for i in range(num_nodes):
		if P[i]>0:
			P[i] = 1
		if Q[i]>0:
			Q[i] = 1
	partial_sums = P - Q
	for i in range(num_nodes - 1):
		val = partial_sums[i]
		partial_sums[Tint[i]] += val
		Z += lint[i, Tint[i]]*abs(val)
	return Z

def EMDUnifrac_unweighted_flow(Tint, lint, nodes_in_order, P, Q):
	'''
	(Z, F) = EMDUnifrac_unweighted_flow(Tint, lint, nodes_in_order, P, Q)
	This function takes the ancestor dictionary Tint, the lengths dictionary lint, the basis nodes_in_order
	and two probability vectors P and Q (typically P = envs_prob_dict[samples[i]], Q = envs_prob_dict[samples[j]]).
	Returns the unweighted Unifrac distance Z and the flow F. The flow F is a dictionary with keys of the form (i,j) where
	F[(i,j)] == 1 means that in the calculation of the Unifrac distance, a total mass of 1 was moved from the node
	nodes_in_order[i] to the node nodes_in_order[j].
	'''
	num_nodes = len(nodes_in_order)
	F = dict()
	G = dict()
	Z = 0
	w = np.zeros(num_nodes)
	pos = dict()
	neg = dict()
	for i in range(num_nodes):
		pos[i] = set([])
		neg[i] = set([])
	for i in range(num_nodes):
		if P[i] > 0:
			P[i] = 1
		if Q[i] > 0:
			Q[i] = 1
		if P[i]>0 and Q[i]>0:
			F[(i,i)] = np.minimum(P[i],Q[i])
		G[(i,i)] = P[i] - Q[i]
		if P[i] > Q[i]:
			pos[i].add(i)
		elif P[i] < Q[i]:
			neg[i].add(i)
		posremove = set()
		negremove = set()
		for j in pos[i]:
			for k in neg[i]:
				if (j not in posremove) and (k not in negremove):
					val = np.minimum(G[(i,j)], -G[(i,k)])
					if val > 0:
						F[(j,k)] = np.minimum(G[(i,j)], -G[(i,k)])
						G[(i,j)] = G[(i,j)] - val
						G[(i,k)] = G[(i,k)] + val
						Z = Z + (w[j] + w[k])*val
					if G[(i,j)] == 0:
						posremove.add(j)
					if G[(i,k)] == 0:
						negremove.add(k)
		pos[i].difference_update(posremove)
		neg[i].difference_update(negremove)
		if i < num_nodes-1:
			for j in pos[i].union(neg[i]):
					if (Tint[i],j) in G:
						G[(Tint[i],j)] = G[(Tint[i],j)] + G[(i,j)]
					else:
						G[(Tint[i],j)] = G[(i,j)]
					w[j] = w[j] + lint[i,Tint[i]]
			pos[Tint[i]] |= pos[i]
			neg[Tint[i]] |= neg[i]
	return (Z, F)  # The returned flow is on the basis nodes_in_order and is given in sparse matrix dictionary format. eg {(0,0):.5,(1,2):.5}


