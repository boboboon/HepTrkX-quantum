# Author: Cenk Tüysüz
# Date: 29.08.2019
# First attempt to test QuantumEdgeNetwork
# Run this code the train and test the network

import matplotlib.pyplot as plt
import pennylane as qml 
from pennylane import numpy as np
from datasets.hitgraphs import HitGraphDataset
import sys, time
import multiprocessing

dev1 = qml.device("default.qubit", wires=6)

@qml.qnode(dev1)
def TTN_edge_forward(edge,theta_learn):
	# Takes the input and learning variables and applies the
	# network to obtain the output
	
	# STATE PREPARATION
	for i in range(len(edge)):
		qml.RY(edge[i],wires=i)
	# APPLY forward sequence
	qml.RY(theta_learn[0],wires=0)
	qml.RY(theta_learn[1],wires=1)
	qml.CNOT(wires=[0,1])
	qml.RY(theta_learn[2],wires=2)
	qml.RY(theta_learn[3],wires=3)
	qml.CNOT(wires=[2,3])
	qml.RY(theta_learn[4],wires=4)
	qml.RY(theta_learn[5],wires=5)
	qml.CNOT(wires=[5,4])
	qml.RY(theta_learn[6],wires=1)
	qml.RY(theta_learn[7],wires=3)
	qml.CNOT(wires=[1,3])
	qml.RY(theta_learn[8],wires=3)
	qml.RY(theta_learn[9],wires=4)
	qml.CNOT(wires=[3,4])
	qml.RY(theta_learn[10],wires=4)
		
	return(qml.expval(qml.PauliZ(wires=4)))

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

def loss_fn(edge_array,y,theta_learn,class_weight,loss_array):
	loss = 0.
	for i in range(len(y)):
		loss +=(((TTN_edge_forward(edge_array[i],theta_learn)+1)/2 - y[i])**2)*class_weight[int(y[i])]
	loss_array.append(loss)

def cost_fn(edge_array,y,theta_learn):
	jobs         = []
	n_threads    = 8
	n_edges      = len(y)
	n_feed       = n_edges//n_threads
	n_class      = [n_edges - sum(y), sum(y)]
	class_weight = [n_edges/(n_class[0]*2), n_edges/(n_class[1]*2)]
	manager        = multiprocessing.Manager()
	loss_array     = manager.list()
	for thread in range(n_threads):
		start = thread*n_feed
		end   = (thread+1)*n_feed
		if thread==(n_threads-1):   
			p = multiprocessing.Process(target=loss_fn,args=(edge_array[start:,:],y[start:],theta_learn,class_weight,loss_array,))
		else:
			p = multiprocessing.Process(target=loss_fn,args=(edge_array[start:end,:],y[start:end],theta_learn,class_weight,loss_array,))   
		jobs.append(p)
		p.start()
	# WAIT for jobs to finish
	for proc in jobs: 
		proc.join()

	return sum(loss_array)/n_edges


def gradient(edge_array,y,theta_learn,class_weight,gradient_array):
	grad = np.zeros(len(theta_learn))
	for i in range(len(edge_array)):
		dcircuit = qml.grad(TTN_edge_forward, argnum=1)
		grad += dcircuit(edge_array[i],theta_learn)*class_weight[int(y[i])]
	gradient_array.append(grad)	

def grad_fn(edge_array,y,theta_learn):
	jobs         = []
	n_threads    = 8
	n_edges      = len(y)
	n_feed       = n_edges//n_threads
	n_class      = [n_edges - sum(y), sum(y)]
	class_weight = [n_edges/(n_class[0]*2), n_edges/(n_class[1]*2)]
	manager        = multiprocessing.Manager()
	gradient_array  = manager.list()
	for thread in range(n_threads):
		start = thread*n_feed
		end   = (thread+1)*n_feed
		if thread==(n_threads-1):   
			p = multiprocessing.Process(target=gradient,args=(edge_array[start:,:],y[start:],theta_learn,class_weight,gradient_array,))
		else:
			p = multiprocessing.Process(target=gradient,args=(edge_array[start:end,:],y[start:end],theta_learn,class_weight,gradient_array,))   
		jobs.append(p)
		p.start()
	# WAIT for jobs to finish
	for proc in jobs: 
		proc.join()

	avg_grad = sum(gradient_array)/n_edges
	with open('log_gradient.csv', 'a') as f:
		for item in avg_grad:
			f.write('%.4f,' % item)
		f.write('\n')

	return avg_grad	

############################################################################################
##### MAIN ######
#client = Client(processes=False, threads_per_worker=1, n_workers=8, memory_limit='2GB')

#client
if __name__ == '__main__':
	
	theta_learn = np.random.rand(11)*np.pi*2 / np.sqrt(11)
	#input_dir = '/home/cenktuysuz/MyRepos/HepTrkX-quantum/data/hitgraphs'
	#input_dir = '/Users/cenk/Repos/HEPTrkX-quantum/data/hitgraphs_big'
	input_dir = 'data\hitgraphs_big'
	n_files = 16*100
	n_epoch = 10
	data = HitGraphDataset(input_dir, n_files)
	loss_log = np.zeros(n_files*n_epoch)
	theta_log = np.zeros((n_files*n_epoch,11))
	
	#accuracy[0] = test_accuracy(theta_learn)
	print('Training is starting!')
	#opt = qml.GradientDescentOptimizer(stepsize=0.01)
	opt = qml.AdamOptimizer(stepsize=0.01, beta1=0.9, beta2=0.99,eps=1e-08)

	for epoch in range(n_epoch): 
		for n_file in range(n_files):
			t0 = time.time()
			X,Ro,Ri,y = data[n_file]
			if n_file%2==0: # Section Correction: even files have negative z 
				X[:,2] = -X[:,2]
			bo    = np.dot(Ro.T, X)
			bi    = np.dot(Ri.T, X)
			B     = np.concatenate((bo,bi),axis=1)
			B     = map2angle(B)
			
			# Update learning variables
			theta_learn = opt.step(lambda v: cost_fn(B,y,v),theta_learn,lambda z: grad_fn(B,y,theta_learn))
			theta_learn = theta_learn % (2*np.pi)
			theta_log[n_file*(epoch+1),:] = theta_learn
			
			loss_log[n_file*(epoch+1)] = cost_fn(B,y,theta_learn)
			t = time.time() - t0
			print('Epoch: %d, Batch: %d, Loss: %.4f, Elapsed: %dm%ds' % (epoch+1, n_file+1, loss_log[n_file*(epoch+1)], t / 60, t % 60)  )
			
			# Log the result every update  

			with open('log_theta.csv', 'a') as f:
				for item in theta_learn:
					f.write('%.4f,' % item)
				f.write('\n')

			with open('log_loss.csv', 'a') as f:
				f.write('%.4f\n' % loss_log[n_file*(epoch+1)])	

		 	# Plot the result every update  

			x = [(i+1) for i  in range(n_file*(epoch+1)+1)]
			plt.clf()
			for i in range(11):
				plt.plot(x,theta_log[:n_file*(epoch+1)+1,i],marker='o',label=r'$\theta_{'+str(i)+'}$')
			plt.xlabel('Update')
			plt.ylabel(r'Angle (0 - 2$\pi$)')
			plt.savefig('png\statistics_angle.png')
	
			plt.clf()
			plt.plot(x,loss_log[:n_file*(epoch+1)+1],marker='o')
			plt.xlabel('Update')
			plt.ylabel('Loss')
			plt.savefig('png\statistics_loss.png')