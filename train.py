# Calculates gradients of a pennylane quantum circuit using tensorflow
import sys, os, time, datetime, csv, yaml, argparse
sys.path.append(os.path.abspath(os.path.join('.')))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Turn off warnings and errors 
# import internal
from tools import *
from test import *
# import external
import tensorflow as tf
import numpy as np
from random import shuffle
############################################################################################
def gradient(edge_array,label):
	# Calculate weights for labels
	n_edges      = len(labels)
	n_class      = [n_edges - sum(labels), sum(labels)]
	class_weight = [n_edges/(n_class[0]*2), n_edges/(n_class[1]*2)]	

	# Calculate weighted loss and gradients
	with tf.GradientTape() as tape:
		loss = tf.reduce_mean(tf.keras.losses.binary_crossentropy(label,block(edge_array)) * np.array([class_weight[int(labels[i])] for i in range(n_edges)]))
		return loss, tape.gradient(loss,block.trainable_variables)
############################################################################################
if __name__ == '__main__':
	# Tensorflow settings
	tf.keras.backend.set_floatx('float64')
	tf.autograph.set_verbosity(2) # don't print warning
	
        # Read config file
	config = load_config(parse_args())

	# Delete old logs
	if config['run_type'] == 'new_run':
		delete_all_logs(config['log_dir'])
	 	
	# Load data
	train_data = get_dataset(config['train_dir'], config['n_train'])
	train_list = [i for i in range(config['n_train'])]

	# Select CPU or GPU
	os.environ["CUDA_VISIBLE_DEVICES"] = config['gpu']
	os.environ['OMP_NUM_THREADS'] = str(config['n_thread'])
		
	# Load network
	if config['network'] == 'TTN' and  config['hid_dim'] == 1:	 # load q. networks with 1 Hid. Dim. 
		from qnetworks.TTN1 import GNN
	elif config['network'] == 'TTN' and config['hid_dim'] == 2:     # load q. networks with 2 Hid. Dim. 
		from qnetworks.TTN2 import GNN
	elif config['network'] == 'TTN' and config['hid_dim'] == 0:     # load q. networks with 0 Hid. Dim. 
		from qnetworks.TTN0 import GNN
	elif config['network'] == 'MERA' and config['hid_dim'] == 1:     # load q. networks with 1 Hid. Dim. 
		from qnetworks.MERA1 import GNN
	elif config['network'] == 'MPS' and config['hid_dim'] == 1:     # load q. networks with 1 Hid. Dim. 
		from qnetworks.MPS1 import GNN
	elif config['network'] == 'QGNN' and config['hid_dim'] == 5:     # load q. networks with 5 Hid. Dim. 
		from qnetworks.GNN5 import GNN
	elif config['network'] == 'CGNN':                                # load classical network
		from qnetworks.CGNN import GNN
		tf.config.threading.set_inter_op_parallelism_threads(config['n_thread'])
	elif config['network'] == 'QGNN_general' and config['hid_dim'] == 1:     # load q. networks with 2 Hid. Dim. 
		from qnetworks.GNN1_general import GNN
	elif config['network'] == 'TEST' and config['hid_dim'] == 1:     # load q. networks with 2 Hid. Dim. 
		from qnetworks.TEST import GNN
		tf.config.threading.set_inter_op_parallelism_threads(config['n_thread'])
	elif config['network'] == 'TTN_noisy' and config['hid_dim'] == 1:
		from qnetworks.TTN1_noisy import GNN
	else:
		RaiseValueError('You chose wrong config settings or this setting is not implemented yet!')

	# Setup the network
	block = GNN(config)
	opt = tf.keras.optimizers.Adam(learning_rate=config['lr'])

	'''
	print(block.trainable_variables)
	if config['log_verbosity']>=2:			
		# Log Learning variables
		log_tensor_array(block.trainable_variables[0],config['log_dir'], 'log_params_IN.csv') 
		log_tensor_array(block.trainable_variables[1],config['log_dir'], 'log_params_EN.csv') 
		log_tensor_array(block.trainable_variables[2],config['log_dir'], 'log_params_NN.csv') 
	'''			
	# Test the validation set
	test_validation(config,block)
	
	########################################## BEGIN TRAINING ########################################## 

	print(str(datetime.datetime.now()) + ': Training is starting!')
	for epoch in range(config['n_epoch']): 
		shuffle(train_list) # shuffle the order every epoch
		for n_step in range(config['n_train']):
			t0 = time.time()

			# Update Learning Variables
			graph_array, labels = preprocess(train_data[train_list[n_step]])
			loss, grads = gradient(graph_array,labels)
			opt.apply_gradients(zip(grads, block.trainable_variables))
			
			t = time.time() - t0

			# Print summary
			print(str(datetime.datetime.now()) + ": Epoch: %d, Batch: %d, Loss: %.4f, Elapsed: %dm%ds" % (epoch+1, n_step+1, loss ,t / 60, t % 60) )

			# Log summary 
			with open(config['log_dir']+'summary.csv', 'a') as f:
				f.write('Epoch: %d, Batch: %d, Loss: %.4f, Elapsed: %dm%ds\n' % (epoch+1, n_step+1, loss, t / 60, t % 60) )
			
			# Log loss
			with open(config['log_dir'] + 'log_loss.csv', 'a') as f:
				f.write('%.4f\n' %loss)	
			

			if config['log_verbosity']>=2:			
				# Log gradients
				log_tensor_array(grads[0],config['log_dir'], 'log_grads_IN.csv') 
		
				with open(config['log_dir'] + 'log_grads_IN.csv', 'a') as f:
					f.write('%f,\n' %grads[1].numpy())
		
				with open(config['log_dir'] + 'log_grads_EN.csv', 'a') as f:
					for item in grads[2].numpy():
						f.write('%f,' %item)
					f.write('\n')	
				
				with open(config['log_dir'] + 'log_grads_NN.csv', 'a') as f:
					for item in grads[3].numpy():
						f.write('%f,' %item)
					f.write('\n')	
			
				# Log Learning variables
				log_tensor_array(block.trainable_variables[0],config['log_dir'], 'log_params_IN.csv') 
				with open(config['log_dir'] + 'log_params_IN.csv', 'a') as f:
					f.write('%f,\n' %block.trainable_variables[1].numpy())
					
				with open(config['log_dir'] + 'log_params_EN.csv', 'a') as f:
					for item in block.trainable_variables[2].numpy():
						f.write('%f,' %item)
					f.write('\n')	
				
				with open(config['log_dir'] + 'log_params_NN.csv', 'a') as f:
					for item in block.trainable_variables[3].numpy():
						f.write('%f,' %item)
					f.write('\n')	
			
			# Test every TEST_every
			if (n_step+1)%config['TEST_every']==0:
					test_validation(config,block)
					#test(train_data,config['n_train'],testing='train')

		# Test the validation set after every epoch
		#test_validation(config,block)

	print(str(datetime.datetime.now()) + ': Training completed!')

	########################################## END TRAINING ##########################################  


	





