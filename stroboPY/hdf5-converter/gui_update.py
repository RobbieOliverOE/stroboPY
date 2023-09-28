import PyQt5.uic

fpath = 'gui.ui'

with open('gui.py','w') as file:
    PyQt5.uic.compileUi(fpath, file)
