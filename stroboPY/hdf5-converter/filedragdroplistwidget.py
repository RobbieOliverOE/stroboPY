from PyQt5 import QtGui, QtCore, QtWidgets
#import sys
            
class FileDragDropListWidget(QtWidgets.QListWidget):    
    def __init__(self, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        #self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)

    def mimeTypes(self):
        mimetypes = super().mimeTypes()
        mimetypes.append('text/uri-list')
        return mimetypes

    def dropMimeData(self, index, data, action):
        if data.hasUrls():
            for url in data.urls():
                item = QtWidgets.QListWidgetItem(str(url.toLocalFile()))
                self.addItem(item)
                self.setCurrentItem(item)
            return True
        else:
            return False
            #return super().dropMimeData(index, data, action)
            
            
#class MyWindow(QtWidgets.QWidget):
#    
#    def __init__(self):
#        super(MyWindow,self).__init__()
#        self.setGeometry(100,100,300,400)
#        self.setWindowTitle("Filenames")
#
#        self.btn = CustomLabel(self)
#        self.btn.setGeometry(QtCore.QRect(90, 90, 61, 51))
#        #self.btn.setText("Change Me!")
#        layout = QtWidgets.QVBoxLayout(self)
#        layout.addWidget(self.btn)
#        self.setLayout(layout)
#        
#
#if __name__ == '__main__':
#    app = QtWidgets.QApplication(sys.argv)
#    window = MyWindow()
#    window.show()
#    sys.exit(app.exec_())