# Transfer learning using Keras and Tensorflow.
# Written by Rahul Remanan and MOAD (https://www.moad.computer) machine vision team.
# For more information contact: info@moad.computer
# License: MIT open source license (
# Repository: https://github.com/rahulremanan/python_tutorial
import argparse
import os
import time
import sys
import glob
import h5py
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import tensorflow
import keras
import PIL
from collections import defaultdict
from keras.applications.inception_v3 import InceptionV3, preprocess_input
from keras.models import Model, model_from_json
from keras.layers import Dense, GlobalAveragePooling2D, Dropout
from keras.preprocessing.image import ImageDataGenerator
from keras.optimizers import SGD, RMSprop, Adagrad

IM_WIDTH, IM_HEIGHT = 299, 299                                                  # Fixed input image size for Inception version 3
DEFAULT_EPOCHS = 100
DEFAULT_BATCHES = 20
FC_SIZE = 4096
DEFAULT_DROPOUT = 0.1
NB_LAYERS_TO_FREEZE = 169

sgd = SGD(lr=1e-7, decay=0.5, momentum=1, nesterov=True)
rms = RMSprop(lr=1e-7, rho=0.9, epsilon=1e-08, decay=0.0)
ada = Adagrad(lr=1e-3, epsilon=1e-08, decay=0.0)
    
DEFAULT_OPTIMIZER = ada

def generate_timestamp():
    timestring = time.strftime("%Y_%m_%d-%H_%M_%S")
    print ("Time stamp generated: " + timestring)
    return timestring

timestr = generate_timestamp()

def is_valid_file(parser, arg):
    if not os.path.isfile(arg):
        parser.error("The file %s does not exist ..." % arg)
    else:
        return arg
    
def is_valid_dir(parser, arg):
    if not os.path.isdir(arg):
        parser.error("The folder %s does not exist ..." % arg)
    else:
        return arg
    
def string_to_bool(val):
    if val.lower() in ('yes', 'true', 't', 'y', '1', 'yeah'):
        return True
    elif val.lower() in ('no', 'false', 'f', 'n', '0', 'none'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected ...')

def get_nb_files(directory):
  if not os.path.exists(directory):
    return 0
  cnt = 0
  for r, dirs, files in os.walk(directory):
    for dr in dirs:
      cnt += len(glob.glob(os.path.join(r, dr + "/*")))
  return cnt

def setup_to_transfer_learn(model, base_model, optimizer):
  for layer in base_model.layers:
    layer.trainable = False
  model.compile(optimizer=optimizer, 
                loss='categorical_crossentropy', metrics=['accuracy'])
  return model

def add_new_last_layer(base_model, nb_classes):                                # Add the fully connected convolutional neural network layer
  try:
      dropout = args.dropout[0]
  except:
      dropout = DEFAULT_DROPOUT
  x = base_model.output
  x = Dropout(dropout)(x)
  x = GlobalAveragePooling2D()(x)
  x = Dropout(dropout)(x)
  x = Dense(FC_SIZE, activation='relu')(x)
  x = Dropout(dropout)(x)
  x = Dense(FC_SIZE, activation='relu')(x)
  x = Dropout(dropout)(x)                                      # New fully connected layer, random init
  predictions = Dense(nb_classes, activation='softmax')(x)                      # New softmax layer
  model = Model(inputs=base_model.input, outputs=predictions)
  return model

def setup_to_finetune(model, optimizer):                                        # Freeze the bottom NB_LAYERS and retrain the remaining top layers
  for layer in model.layers[:NB_LAYERS_TO_FREEZE]:
     layer.trainable = False
  for layer in model.layers[NB_LAYERS_TO_FREEZE:]:
     layer.trainable = True
  model.compile(optimizer=optimizer, loss='categorical_crossentropy', 
                metrics=['accuracy'])
  return model

def save_model(args, name, model):
    file_loc = args.output_dir[0]
    file_pointer = os.path.join(file_loc+"//trained_"+ timestr)
    model.save_weights(os.path.join(file_pointer + "_weights"+str(name)+".model"))
    # serialize model to JSON
    model_json = model.to_json()
    with open(os.path.join(file_pointer+"_config"+str(name)+".json"), "w") as json_file:
        json_file.write(model_json)
    print ("Saved the trained model weights to: " + 
           str(os.path.join(file_pointer + "_weights"+str(name)+".model")))
    print ("Saved the trained model configuration as a json file to: " + 
           str(os.path.join(file_pointer+"_config"+str(name)+".json")))

def generate_labels(args):
    file_loc = args.output_dir[0]
    file_pointer = os.path.join(file_loc+"//trained_labels")
    
    data_dir = args.train_dir[0]
    val_dir_ = args.val_dir[0]
    
    dt = defaultdict(list)
    dv = defaultdict(list)
    
    for root, subdirs, files in os.walk(data_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            assert file_path.startswith(data_dir)
            suffix = file_path[len(data_dir):]
            suffix = suffix.lstrip("/")
            label = suffix.split("/")[0]
            dt[label].append(file_path)
            
    for root, subdirs, files in os.walk(val_dir_):
        for filename in files:
            file_path = os.path.join(root, filename)
            assert file_path.startswith(val_dir_)
            suffix = file_path[len(val_dir_):]
            suffix = suffix.lstrip("/")
            label = suffix.split("/")[0]
            dv[label].append(file_path)

    labels = sorted(dt.keys())
    val_labels = sorted(dv.keys())
    
    if set(labels) == set (val_labels):
        with open(os.path.join(file_pointer+".json"), "w") as json_file:
            json.dump(labels, json_file)
    else:
      print ("Mismatched training and validation data labels ...")
      print ("Sub-folder names do not match between training and validation directories ...")
      sys.exit(1)

    return labels

def generate_plot(args, name, model_train):
    gen_plot = args.plot[0]
    if gen_plot==True:
        plot_training(args, name, model_train)
    else:
        print ("No training summary plots generated ...")
        print ("Set: --plot True for creating training summary plots")

def plot_training(args, name, history):
  output_loc = args.output_dir[0]
  
  output_file_acc = os.path.join(output_loc+
                                 "//training_plot_acc_"+timestr+str(name)+".png")
  output_file_loss = os.path.join(output_loc+
                                  "//training_plot_loss_"+timestr+str(name)+".png")
  fig_acc = plt.figure()
  plt.plot(history.history['acc'])
  plt.plot(history.history['val_acc'])
  plt.title('model accuracy')
  plt.ylabel('accuracy')
  plt.xlabel('epoch')
  plt.legend(['train', 'test'], loc='upper left')
  fig_acc.savefig(output_file_acc, dpi=fig_acc.dpi)
  print ("Successfully created the training accuracy plot: " 
         + str(output_file_acc))
  plt.close()

  fig_loss = plt.figure()
  plt.plot(history.history['loss'])
  plt.plot(history.history['val_loss'])
  plt.title('model loss')
  plt.ylabel('loss')
  plt.xlabel('epoch')
  plt.legend(['train', 'test'], loc='upper left')
  fig_loss.savefig(output_file_loss, dpi=fig_loss.dpi)
  print ("Successfully created the loss function plot: " 
         + str(output_file_loss))
  plt.close()
        
def train(args): 
  optimizer = args.optimizer[0]
  lr = args.learning_rate[0]
  decay = args.decay[0]
  if optimizer == 'sgd' or optimizer == 'SGD' or optimizer == 'Sgd':
    optimizer = SGD(lr=lr, decay=decay, momentum=1, nesterov=True)
    print ("Using SGD as the optimizer ...")
  elif optimizer == 'rms' or optimizer == 'SGD' or optimizer == 'RMSprop' or optimizer == 'rmsprop' or optimizer == 'Rmsprop':
    optimizer = RMSprop(lr=lr, rho=0.9, epsilon=1e-08, decay=decay)
    print ("Using RMSProp as the optimizer ...")
  elif optimizer == 'ada' or optimizer == 'ADA' or optimizer == 'Ada':
    optimizer = Adagrad(lr=lr, epsilon=1e-08, decay=decay)
    print ("Using Adagrad as the optimizer ...")
  else:
      optimizer = DEFAULT_OPTIMIZER
                                                               # Transfer learning and fine-tuning for training
  nb_train_samples = get_nb_files(args.train_dir[0])
  nb_classes = len(glob.glob(args.train_dir[0] + "/*"))
  
  print ("Total number of training samples = " + str(nb_train_samples))
  print ("Number of training classes = " + str(nb_classes))
  
  nb_val_samples = get_nb_files(args.val_dir[0])
  nb_val_classes = len(glob.glob(args.val_dir[0] + "/*"))
  
  print ("Total number of validation samples = " + str(nb_val_samples))
  print ("Number of validation classes = " + str(nb_val_classes))
  
  if nb_val_classes == nb_classes:
      print ("Initiating training session ...")
  else:
      print ("Mismatched number of training and validation data classes ...")
      print ("Unequal number of sub-folders found between train and validation directories ...")
      print ("Each sub-folder in train and validation directroies are treated as a separate class ...")
      print ("Correct this mismatch and re-run ...")
      print ("Now exiting ...")
      sys.exit(1)
      
  nb_epoch = int(args.epoch[0])
  batch_size = int(args.batch[0])
  
  train_datagen =  ImageDataGenerator(preprocessing_function=preprocess_input,
      rotation_range=30,
      width_shift_range=0.2,
      height_shift_range=0.2,
      shear_range=0.2,
      zoom_range=0.2,
      horizontal_flip=True)
  
  test_aug = args.test_aug[0]  
  
  if test_aug==True:
      test_datagen = ImageDataGenerator(
        preprocessing_function=preprocess_input,
          rotation_range=30,
          width_shift_range=0.2,
          height_shift_range=0.2,
          shear_range=0.2,
          zoom_range=0.2,
          horizontal_flip=True)
  else:
      test_datagen = ImageDataGenerator(rescale=1. / 255)
      
  print ("Generating training data: ... ")

  train_generator = train_datagen.flow_from_directory(args.train_dir[0],
    target_size=(IM_WIDTH, IM_HEIGHT),
    batch_size=batch_size,
    class_mode='categorical')
  
  print ("Generating validation data: ... ")

  validation_generator = test_datagen.flow_from_directory(args.val_dir[0],
    target_size=(IM_WIDTH, IM_HEIGHT),
    batch_size=batch_size,
    class_mode='categorical')
  
  base_model = InceptionV3(weights='imagenet', include_top=False)               # Model argument: include_top=False excludes the final FC layer
  model = add_new_last_layer(base_model, nb_classes)
  print ("Base model for transfer learning: Inception version 3 ...")
  
  labels = generate_labels(args)
  
  model_summary_ = args.model_summary[0]
  
  if model_summary_ == True:
      print (model.summary())
  else:
      print ("Successfully loaded Inception version 3 for training ...")
    
  load_weights_ = args.load_weights[0]
  fine_tune_model = args.fine_tune[0]
  
  if load_weights_ == True:      
      try:
          with open(args.config_file[0]) as json_file:
              model_json = json_file.read()
          model = model_from_json(model_json)
      except:
          model = model
      try:
          model.load_weights(args.weights_file[0])
          print ("Loaded model weights from: " + str(args.weights_file[0]))
      except:
          print ("Error loading model weights ...")
          print ("Loaded default model weights ...")
  else:
      model = model
      print ("Tabula rasa ...")
      
  if fine_tune_model == True:
      print ("Fine tuning Inception v3 ...")
      setup_to_finetune(model, optimizer)
  else:
      print ("Transfer learning using Inception v3 ...")
      setup_to_transfer_learn(model, base_model, optimizer)
            
  print ("Initializing training with  class labels: " + 
         str(labels))
  
  model_train = model.fit_generator(train_generator,
                  epochs=nb_epoch,
                  steps_per_epoch=nb_train_samples // batch_size,
                  validation_data=validation_generator,
                  validation_steps=nb_val_samples // batch_size,
                  class_weight='auto')
  
  if fine_tune_model == True:
      save_model(args, "_ft_", model)
      generate_plot(args, "_ft_", model_train)
  else:
      save_model(args, "_tl_", model)
      generate_plot(args, "_tl_", model_train)
      
  
def get_user_options():
    a = argparse.ArgumentParser()
    
    a.add_argument("--training_directory", 
                 help = "Specify folder contraining the training files ...", 
                 dest = "train_dir", 
                 required = True, 
                 type=lambda x: is_valid_dir(a, x), 
                 nargs=1)
    
    a.add_argument("--validation_directory", 
                   help = "Specify folder containing the validation files ...", 
                   dest = "val_dir", 
                   required = True, 
                   type=lambda x: is_valid_dir(a, x), 
                   nargs=1)
    
    a.add_argument("--epochs", 
                   help = "Specify epochs for training ...", 
                   dest = "epoch", 
                   default=[DEFAULT_EPOCHS], 
                   required=False, 
                   type = int, 
                   nargs=1)
    
    a.add_argument("--batches", help = "Specify batches for training ...", 
                   dest = "batch", 
                   default=[DEFAULT_BATCHES], 
                   required=False, 
                   type = int, 
                   nargs=1)
    
    a.add_argument("--weights_file", 
                   help = "Specify pre-trained model weights for training ...", 
                   dest = "weights_file", 
                   required=False,
                   type=lambda x: is_valid_file(a, x),
                   nargs=1)
    
    a.add_argument("--config_file", 
                   help = "Specify pre-trained model configuration file ...", 
                   dest = "config_file",  
                   required=False,
                   type=lambda x: is_valid_file(a, x),
                   nargs=1)
    
    a.add_argument("--output_directory", 
                   help = "Specify output folder ...", 
                   dest = "output_dir", 
                   required = True, 
                   type=lambda x: is_valid_dir(a, x),
                   nargs=1)
    
    a.add_argument("--train_model", 
                   help = "Specify if the model should be trained ...", 
                   dest = "train_model", 
                   required=True, 
                   default=[True], 
                   nargs=1, 
                   type = string_to_bool)
    
    a.add_argument("--load_weights", 
                   help = "Specify if pre-trained model should be loaded ...", 
                   dest = "load_weights", 
                   required=False, 
                   default=[False], 
                   nargs=1, 
                   type = string_to_bool)
    
    a.add_argument("--fine_tune", 
                   help = "Specify model should be fine tuned ...", 
                   dest = "fine_tune", 
                   required=False, 
                   default=[True], 
                   nargs=1, 
                   type = string_to_bool)
    
    a.add_argument("--test_augmentation", 
                   help = "Specify image augmentation for test dataset ...", 
                   dest = "test_aug", 
                   required=False, 
                   default=[False], 
                   nargs=1, 
                   type = string_to_bool)
    
    a.add_argument("--plot", 
                   help = "Specify if a plot should be generated ...", 
                   dest = "plot", 
                   required=False, 
                   default=[True], 
                   nargs=1, 
                   type = string_to_bool)
    
    a.add_argument("--summary", 
                   help = "Specify if a summary should be generated ...", 
                   dest = "model_summary", 
                   required=False, 
                   default=[False], 
                   type = string_to_bool,
                   nargs=1)
    
    a.add_argument("--dropout", 
                   help = "Specify values for dropout function ...", 
                   dest = "dropout", 
                   required=False, 
                   default=[0.4], 
                   type = float,
                   nargs=1)
    
    a.add_argument("--learning_rate", 
                   help = "Specify values for learning rate ...", 
                   dest = "learning_rate", 
                   required=False, 
                   default=[1e-07], 
                   type = float,
                   nargs=1)
    
    a.add_argument("--decay", 
                   help = "Specify values for decay function ...", 
                   dest = "decay", 
                   required=False, 
                   default=[0.0], 
                   type = float,
                   nargs=1)
    
    a.add_argument("--optimizer", 
                   help = "Specify the type of optimizer to choose from. Options are: rms, ada and sgd ...", 
                   dest = "optimizer", 
                   required=False, 
                   default=['rms'], 
                   nargs=1)
    
    args = a.parse_args()
    
    return args

if __name__=="__main__":
    args = get_user_options()

    if ((not os.path.exists(args.train_dir[0])) 
        or 
    (not os.path.exists(args.val_dir[0])) 
        or 
    (not os.path.exists(args.output_dir[0]))):
      print("Specified directories do not exist ...")
      sys.exit(1)
    
    train_model = args.train_model[0]
    
    if train_model ==True:
        print ("Training sesssion initiated ...")
        train(args)
    else:
        print ("Nothing to do here ...")
        print ("Try setting the --train_model flag to True ...")
        print ("For more help, run with -h flag ...")
        sys.exit(1)