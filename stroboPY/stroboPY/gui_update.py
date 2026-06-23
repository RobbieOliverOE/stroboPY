import PyQt5.uic

fpath = 'gui.ui'

with open('gui.py','w', encoding="utf-8") as file:
    PyQt5.uic.compileUi(fpath, file)

# @note The utf-8 encoding is neccessary for the Δ (delta) symbol in the GUI.