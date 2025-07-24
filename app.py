# Demo objective 
# Demo 1: Given an adress and date (optional) in natural language as input, get the data from TE-JAPAN, convert an image accordingly.



import sys
from PyQt5.QtWidgets import QApplication
from interface import AddressForm
from googleAPI import addressToCoordinates, getStreetViewImage

def handle(data):
    print("User submitted →", data)

    

    



app = QApplication(sys.argv)
w   = AddressForm()
w.data_submitted.connect(handle)
w.show()
sys.exit(app.exec_())
