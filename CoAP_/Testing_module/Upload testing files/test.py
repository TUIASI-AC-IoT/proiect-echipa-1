#!/usr/bin/env python
# coding: utf-8

# In[1]:


import numpy as np
import timeit 
import matplotlib.pyplot as plotp


# In[2]:


def DFT_slow(x):
    """Calculez TFD pentru vectorul x, conform definitiei"""
    x = np.asarray(x, dtype=float)
    N = x.shape[0]
    n = np.arange(N)
    k = n.reshape((N, 1))
    M = np.exp(-2j * np.pi * k * n / N)
    return np.dot(M, x)


# In[3]:


def FFT(x):
    """Algoritmul recursiv Cooley-Tukey FFT"""
    x = np.asarray(x, dtype=float)
    N = x.shape[0]

    if int(N) % 2 > 0:
        raise ValueError("N nu este putere a lui 2")
    elif int(N) <= 32: # N este mic trebuie optimizat
        return DFT_slow(x)
    else:
        X_even = FFT(x[::2])
        X_odd = FFT(x[1::2])
        factor = np.exp(-2j * np.pi * np.arange(int(N)) / int(N))
        return np.concatenate([X_even + factor[:int(N / 2)] * X_odd, X_even + factor[int(N / 2):] * X_odd])    


# In[4]:


print ("x este un vector oarecare")
x = np.random.random(1024) - 0.5
print ("functiile DFT_slow si np.fft.fft, dau acelasi rezultat? Valorile sunt close")
print (np.allclose(DFT_slow(x), np.fft.fft(x)))
print (np.allclose(FFT(x), np.fft.fft(x)))
t1 = timeit.Timer(lambda: DFT_slow(x))  
print ("DFT_slow: " + str(t1.timeit(5)))
t2 = timeit.Timer(lambda: FFT(x))  
print ("FFT: " + str(t2.timeit(5)))
t3 = timeit.Timer(lambda: np.fft.fft(x))  
print ("np FFT: "+ str(t3.timeit(5)))
ps = np.abs(np.fft.fft(x)**2)
time_step = 1.0/2048.0
freqs = np.fft.fftfreq(x.size, time_step)
idx = np.argsort(freqs)


# In[5]:


#plotp.plot(freqs[idx], ps[idx])


# In[6]:


plotp.plot(freqs[idx], ps[idx])
plotp.show()


# In[ ]:




