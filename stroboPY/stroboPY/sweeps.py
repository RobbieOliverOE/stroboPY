import numpy as np
import os
import h5py
import datetime as dt
import tifffile

class SweepProcessing:
    def __init__(self,times,num_pixels,filename,metadata,cameratype='Andor Zyla 5.5'):
        self.filename = filename.split('.')[0]
        self.cameratype = cameratype
        print(self.cameratype)
        if self.cameratype=='VIS' or self.cameratype=='NIR': # Case for VIS or NIR detectors (pyTA)
            self.ext = '.hdf5'
            self.filename_ext = self.filename+self.ext
            i = 1
            while os.path.isfile(self.filename_ext) is True: # if filename (or filename_i) exists...
                self.filename_ext = self.filename+'_'+str(i)+self.ext # ...write to filename_i (or filename_i+1)
                i += 1
        else: # elif self.cameratype=='Andor Zyla 5.5' or self.cameratype=='Andor Zyla 4.2': # Case for imaging cameras, e.g. Zyla (stroboPY)
            self.ext = '.tif'
            i = 1
            while os.path.isdir(self.filename) is True: # if filename (or filename_i) exists...
                self.filename = self.filename+'_'+str(i) # ...write to filename_i (or filename_i+1)
                i += 1
            self.filename_ext = self.filename+self.ext
        
        self.metadata = metadata
        
        self.sweep_index = 0
        self.times = np.array(times,ndmin=2)
        self.sweep_index_array = np.zeros(shape=(self.times.size,1))
        self.num_pixels = num_pixels
        self.current_data = np.zeros(shape=(self.times.size,self.num_pixels[0],self.num_pixels[1]))
        self.current_data_i_off = np.zeros(shape=(self.times.size,self.num_pixels[0],self.num_pixels[1]))
        self.avg_data = np.zeros(shape=(self.times.size,self.num_pixels[0],self.num_pixels[1]))
        self.avg_data_i_off = np.zeros(shape=(self.times.size,self.num_pixels[0],self.num_pixels[1]))
        self.times_labels = ['%.3f'%(i)+' ps' for i in self.times[0]] # Label each frame with the time delay, in ps

        
    def make_tif_folder(self):
        '''If it doesn't exist, makes a folder for the data for microscopy images, rather than a hdf5 container.'''
        if self.cameratype=='Andor Zyla 5.5'or'Andor Zyla 4.2':
            if not os.path.exists(self.filename):
                os.makedirs(self.filename)

    def add_current_data(self,dtt,i_off,time_point):
        self.current_data[time_point,:,:] = dtt
        self.current_data_i_off[time_point,:,:] = i_off
        if self.sweep_index == 0: # if on the first sweep...
            self.avg_data[time_point,:,:] = dtt
            self.avg_data_i_off[time_point,:,:] = i_off
        else: # ...if on the 2nd sweep and up, add that sweep to the existing sweeps and re-average
            self.avg_data[time_point,:,:] = np.array(((self.avg_data[time_point,:,:]*self.sweep_index_array[time_point])+dtt)/(self.sweep_index_array[time_point]+1))
            self.avg_data_i_off[time_point,:,:] = np.array(((self.avg_data_i_off[time_point,:,:]*self.sweep_index_array[time_point])+i_off)/(self.sweep_index_array[time_point]+1))
        self.sweep_index_array[time_point] = self.sweep_index_array[time_point]+1 
        return
            
    def next_sweep(self):
        self.sweep_index = self.sweep_index+1
        self.current_data = np.zeros(shape=(self.times.size,self.num_pixels[0],self.num_pixels[1]))
        self.current_data_i_off = np.zeros(shape=(self.times.size,self.num_pixels[0],self.num_pixels[1]))
        return
        
#    def save_current_data_old(self,waves):
#        basename = os.path.basename(self.filename)
#        pathname= os.path.dirname(self.filename)
#        new_path = pathname+'/'+basename+'_Sweeps/'
#        new_filename = new_path+basename+'_Sweep_'+str(self.sweep_index+1)+'.dtc'
#        if not os.path.exists(new_path):
#            os.makedirs(new_path)
#        save_data = np.vstack((np.hstack((0,waves)),
#                                np.hstack((self.times.T,
#                                           self.current_data))))
#        np.savetxt(new_filename,save_data,newline='\r\n',delimiter='\t',fmt='%1.4e')
        
    def save_current_data(self,waves=[]):
        # if self.cameratype=='VIS'or'NIR': # Case for VIS or NIR detectors (pyTA)
        # # @todo if adapting pyTA into this, need to adjust for 1D arrays (rather than 2D images)
        #     save_data = np.vstack((np.hstack((0,waves)),
        #                            np.hstack((self.times.T,
        #                                       self.current_data))))
            
        #     with h5py.File(self.filename_ext) as hdf5_file:
        #         dset = hdf5_file.create_dataset('Sweeps/Sweep_'+str(self.sweep_index),data=save_data)
        #         dset.attrs['date'] = str(dt.datetime.now().date()).encode('ascii','ignore')
        #         dset.attrs['time'] = str(dt.datetime.now().time()).encode('ascii','ignore'
        #                                                                   )
        #     pass
        # else: # elif self.cameratype=='Andor Zyla 5.5'or'Andor Zyla 4.2': # Case for imaging cameras, e.g. Zyla (stroboPY)
        print('in save current data, self.sweep_index' + str(self.sweep_index))
        tifffile.imwrite(os.path.join(self.filename,'dII_sweep_'+str(self.sweep_index)+'.tif'), self.current_data.astype('float32'), # supposedly float64 is not supported!
            imagej=True,
            metadata={
                'Labels': self.times_labels,
                },
            )
        tifffile.imwrite(os.path.join(self.filename,'I_off_sweep_'+str(self.sweep_index)+'.tif'), self.current_data_i_off.astype('float32'), # supposedly float64 is not supported!
            imagej=True,
            metadata={
                'Labels': self.times_labels,
                },
            )
        return
        
#    def save_avg_data_old(self,waves):
#        save_data = np.vstack((np.hstack((0,waves)),
#                               np.hstack((self.times.T,
#                                          self.avg_data))))
#        
#        np.savetxt(self.filename,save_data,newline='\r\n',delimiter='\t',fmt='%1.4e')
        
    def save_avg_data(self,waves=[]):
        # if self.cameratype=='VIS'or'NIR': # Case for VIS or NIR detectors (pyTA)
        # # @todo if adapting pyTA into this, need to adjust for 1D arrays (rather than 2D images)
        #     save_data = np.vstack(np.hstack((0,waves)),
        #                           np.hstack((self.times.T,
        #                                      self.avg_data)))
            
        #     with h5py.File(self.filename_ext) as hdf5_file:
        #         try:
        #             dset = hdf5_file['Average']
        #             dset[:,:] = save_data
        #             dset.attrs.modify('end_date',str(dt.datetime.now().date()).encode('ascii','ignore'))
        #             dset.attrs.modify('end_time',str(dt.datetime.now().time()).encode('ascii','ignore'))
        #             dset.attrs.modify('num_sweeps',str(self.sweep_index).encode('ascii','ignore'))
        #         except:
        #             self.save_metadata_initial()
        #             dset = hdf5_file.create_dataset('Average',data=save_data)
        #             dset.attrs['start date'] = str(dt.datetime.now().date()).encode('ascii','ignore')
        #             dset.attrs['start time'] = str(dt.datetime.now().time()).encode('ascii','ignore')
        #             for key,item in self.metadata.items():
        #                 dset.attrs[key] = str(item).encode('ascii','ignore')
        #             dset.attrs['num_sweeps'] = str(self.sweep_index).encode('ascii','ignore')
        # else: # elif self.cameratype=='Andor Zyla 5.5'or'Andor Zyla 4.2': # Case for imaging cameras, e.g. Zyla (stroboPY)
        print('Attempting to save average data!')
        tifffile.imwrite(os.path.join(self.filename,'dII_avg.tif'), self.avg_data.astype('float32'), # supposedly float64 is not supported!
            imagej=True,
            metadata={
                'Labels': self.times_labels,
                },
            )
        tifffile.imwrite(os.path.join(self.filename,'I_off_avg.tif'), self.avg_data_i_off.astype('float32'), # supposedly float64 is not supported!
            imagej=True,
            metadata={
                'Labels': self.times_labels,
                },
            )
        return
    
    def save_metadata(self):
        '''
        # Perform export to human-readable txt file
        '''
        with open(os.path.join(self.filename,'metadata_start.txt'), 'w') as f:
            for key, value in self.metadata.items():
                # Write lines in '{key}: {value}' format
                f.write(f'{key}: {value}\n')
    
'''
Old pyTA stuff below

    def save_metadata_initial(self):
        with h5py.File(self.filename_ext) as hdf5_file:
            data = np.zeros((1,1))
            dset = hdf5_file.create_dataset('Metadata',data=data)
            for key, item in self.metadata.items():
                dset.attrs[key] = str(item).encode('ascii','ignore')
                    
    def save_metadata_each_sweep(self,probe,reference,error):
        with h5py.File(self.filename_ext) as hdf5_file:
            dset = hdf5_file.create_dataset('Spectra/Sweep_'+str(self.sweep_index)+'_Probe_Spectrum',data=probe)
            dset.attrs['date'] = str(dt.datetime.now().date()).encode('ascii','ignore')
            dset.attrs['time'] = str(dt.datetime.now().time()).encode('ascii','ignore')
                
            dset2 = hdf5_file.create_dataset('Spectra/Sweep_'+str(self.sweep_index)+'_Reference_Spectrum',data=reference)
            dset2.attrs['date'] = str(dt.datetime.now().date()).encode('ascii','ignore')
            dset2.attrs['time'] = str(dt.datetime.now().time()).encode('ascii','ignore')
                
            dset3 = hdf5_file.create_dataset('Spectra/Sweep_'+str(self.sweep_index)+'_Error_Spectrum',data=error)
            dset3.attrs['date'] = str(dt.datetime.now().date()).encode('ascii','ignore')
            dset3.attrs['time'] = str(dt.datetime.now().time()).encode('ascii','ignore')
'''