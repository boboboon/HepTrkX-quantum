# Author: Cenk Tüysüz
# Date: 29.08.2019
# First attempt to test QuantumEdgeNetwork
# Run this code the train and test the network

import numpy as np
import matplotlib.pyplot as plt
from qiskit import *
from datasets.hitgraphs import HitGraphDataset
import sys, time
import multiprocessing

def TTN_edge_forward(edge,theta_learn):
	# Takes the input and learning variables and applies the
	# network to obtain the output
	
	q       = QuantumRegister(len(edge))
	c       = ClassicalRegister(1)
	circuit = QuantumCircuit(q,c)
	# STATE PREPARATION
	for i in range(len(edge)):
		circuit.ry(edge[i],q[i])
	# APPLY forward sequence

	circuit.ry(theta_learn[0],q[0])
	circuit.ry(theta_learn[1],q[1])
	circuit.cx(q[0],q[1])

	circuit.ry(theta_learn[2],q[2])
	circuit.ry(theta_learn[3],q[3])
	circuit.cx(q[2],q[3])

	circuit.ry(theta_learn[4],q[4])
	circuit.ry(theta_learn[5],q[5])
	circuit.cx(q[5],q[4]) # reverse the order

	circuit.ry(theta_learn[6],q[1])
	circuit.ry(theta_learn[7],q[3])
	circuit.cx(q[1],q[3])

	circuit.ry(theta_learn[8],q[3])
	circuit.ry(theta_learn[9],q[4])
	circuit.cx(q[3],q[4])

	circuit.ry(theta_learn[10],q[4])
	
	# Qasm Backend
	circuit.measure(q[4],c)
	backend = BasicAer.get_backend('qasm_simulator')
	result = execute(circuit, backend, shots=1000).result()
	counts = result.get_counts(circuit)
	out    = 0
	for key in counts:
		if key=='1':
			out = counts[key]/1000
	
	return(out)

def TTN_edge_back(input_,theta_learn):
	# This function calculates the gradients for all learning 
	# variables numerically and updates them accordingly.
	# TODO: need to choose epsilon properly
	epsilon = np.pi/2 # to take derivative
	gradient = np.zeros(len(theta_learn))
	update = np.zeros(len(theta_learn))
	for i in range(len(theta_learn)):
		## Compute f(x+epsilon)
		theta_learn[i] = (theta_learn[i] + epsilon)%(2*np.pi)
		## Evaluate
		out_plus = TTN_edge_forward(input_,theta_learn)
		## Compute f(x-epsilon)
		theta_learn[i] = (theta_learn[i] - 2*epsilon)%(2*np.pi)
		## Evaluate
		out_minus = TTN_edge_forward(input_,theta_learn)
		# Compute the gradient numerically
		gradient[i] = (out_plus-out_minus)/2
		## Bring theta to its original value
		theta_learn[i] = (theta_learn[i] + epsilon)%(2*np.pi)
	return gradient
def map2angle(B):
	# Maps input features to 0-2PI
	r_min     = 0.
	r_max     = 1.
	phi_min   = -1.
	phi_max   = 1.
	z_min     = 0.
	z_max     = 1.2
	B[:,0] =  (B[:,0]-r_min)/(r_max-r_min) 
	B[:,1] =  (B[:,1]-phi_min)/(phi_max-phi_min) 
	B[:,2] =  (B[:,2]-z_min)/(z_max-z_min) 
	B[:,3] =  (B[:,3]-r_min)/(r_max-r_min) 
	B[:,4] =  (B[:,4]-phi_min)/(phi_max-phi_min) 
	B[:,5] =  (B[:,5]-z_min)/(z_max-z_min)
	return B
def get_loss_and_gradient(edge_array,y,theta_learn,class_weight,loss_array,gradient_array,update_array):
	local_loss     = 0.
	local_gradient = np.zeros(len(theta_learn))
	local_update   = np.zeros(len(theta_learn))
	#print('Edge Array Size: ' + str(len(edge_array)))
	for i in range(len(edge_array)):
		error          = TTN_edge_forward(edge_array[i],theta_learn) - y[i]
		loss           = (error**2)*class_weight[int(y[i])]
		local_loss     += loss
		gradient       = TTN_edge_back(edge_array[i],theta_learn)*class_weight[int(y[i])]
		local_gradient += gradient
		local_update   += 2*error*gradient
		#print('Item: ' + str(i) + ' Loss: ' + str(loss))
	loss_array.append(local_loss)
	gradient_array.append(local_gradient)
	update_array.append(local_update)
def train(B,theta_learn,y):
	jobs         = []
	n_threads    = 8
	n_edges      = len(y)
	n_feed       = n_edges//n_threads
	n_class      = [n_edges - sum(y), sum(y)]
	class_weight = [n_edges/(n_class[0]*2), n_edges/(n_class[1]*2)]
	# RESET variables
	manager        = multiprocessing.Manager()
	loss_array     = manager.list()
	gradient_array = manager.list()
	update_array   = manager.list()
	# Learning variables
	lr = 1
	# RUN Multithread training
	#print('Total edge: ' + str(n_edges))
	for thread in range(n_threads):
		start = thread*n_feed
		end   = (thread+1)*n_feed
		if thread==(n_threads-1):   
			p = multiprocessing.Process(target=get_loss_and_gradient,args=(B[start:,:],y[start:],theta_learn,class_weight,loss_array,gradient_array,update_array,))
		else:
			p = multiprocessing.Process(target=get_loss_and_gradient,args=(B[start:end,:],y[start:end],theta_learn,class_weight,loss_array,gradient_array,update_array,))   
		jobs.append(p)
		p.start()
		#print('Thread: ' + str(thread) + ' started')

	# WAIT for jobs to finish
	for proc in jobs: 
		proc.join()
		#print('Thread ended')
			
	total_loss     = sum(loss_array)
	total_gradient = sum(gradient_array)
	total_update   = sum(update_array)
	## UPDATE WEIGHTS
	average_loss     = total_loss/n_edges
	average_gradient = total_gradient/n_edges
	average_update   = total_update/n_edges
	theta_learn       = (theta_learn - lr*average_update)%(2*np.pi)
	print('Loss: '      + str(average_loss)     )
	print('Gradients: ' + str(average_gradient) )
	print('Updates: '   + str(average_update)   )
	print('Updated Angles : '   + str(theta_learn)      )
	
	with open('log_gradients.csv', 'a') as f:
			for item in average_update:
				f.write('%.4f, ' % item)
			f.write('\n')	
	return theta_learn,average_loss
############################################################################################
##### MAIN ######
#client = Client(processes=False, threads_per_worker=1, n_workers=8, memory_limit='2GB')

#client
if __name__ == '__main__':
	
	theta_learn = np.random.rand(11)*np.pi*2
	#input_dir = '/home/cenktuysuz/MyRepos/HepTrkX-quantum/data/hitgraphs'
	#input_dir = '/Users/cenk/Repos/HEPTrkX-quantum/data/hitgraphs_big'
	input_dir = 'data\hitgraphs_big'
	n_files = 16*100
	data = HitGraphDataset(input_dir, n_files)
	
	theta_log = np.zeros((n_files,11))
	#accuracy[0] = test_accuracy(theta_learn)
	print('Training is starting!')
	for epoch in range(1): 
		for n_file in range(n_files):
			t0 = time.time()
			loss_log = np.zeros(n_files)
			X,Ro,Ri,y = data[n_file]
			if n_file%2==0: # Section Correction: even files have negative z 
				X[:,2] = -X[:,2]
			bo    = np.dot(Ro.T, X)
			bi    = np.dot(Ri.T, X)
			B     = np.concatenate((bo,bi),axis=1)
			B     = map2angle(B)
			
			# Log learning variables
			with open('log_learning.csv', 'a') as f:
				for item in theta_learn:
					f.write('%.4f,' % item)
				f.write('\n')

			# Update learning variables
			theta_learn,loss_log[n_file] = train(B,theta_learn,y)
			theta_log[n_file,:] = theta_learn   

			# Log loss and duration
			t = time.time() - t0
			with open('log_loss.csv', 'a') as f:
				f.write('%d, %.4f, %.2d, %.2d\n' % (n_file+1, loss_log[n_file], t / 60, t % 60))

			# Plot the result every update  
			plt.clf()   
			x = [(i+1) for i  in range(n_file+1)]
			plt.plot(x,loss_log[:n_file+1],marker='o')
			plt.xlabel('Update')
			plt.ylabel('Loss')
			plt.savefig('png\statistics_loss.png')

			plt.clf()
			for i in range(11):
				plt.plot(x,theta_log[:n_file+1,i],marker='o',label=r'$\theta_{'+str(i)+'}$')
			plt.xlabel('Update')
			plt.ylabel(r'Angle (0 - 2$\pi$)')
			plt.savefig('png\statistics_angle.png')

		average_epoch_loss = loss_log.mean()

