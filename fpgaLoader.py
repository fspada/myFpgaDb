from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Table, Column, String, Integer
import os
from threading import Thread
from threading import Lock
import time
import re


class Fpga():

	def __xml2db(self):
		#fpgaSchema = ['model','version','speed','x','y','genericType','tileX',
		#'tileY','specificType','dim','num','primGenType','primX','primY',
		#'primSpecType','attr','primNum']
		while 1:
			line = self.fd.readline()
			if not line:
				return
			words = line.split()
			if words[0] == '<tile':
				row = self.FpgaTable()
				row.model = self.fpgaModel
				row.version=self.fpgaVersion
				row.speed=self.fpgaSpeed
				row.x = words[1].split('"')[1]
				row.y = words[2].split('"')[1]
				obj = re.match(r"(.+)_X([0-9]+)Y([0-9]+)", words[3].split('"')[1])
				if obj:
					row.genericType = obj.group(1)
					row.tileX = obj.group(2)
					row.tileY = obj.group(3)
				else:
					row.genericType = words[3].split('"')[1]
					row.tileX = ""
					row.tileY = ""
				row.specificType = words[4].split('"')[1]
				row.num = words[5].split('"')[1]
				if words[-1][-1] == '>' and len(words[-1]) == 1:
					line = self.fd.readline()
					if not line:
						return
					words = line.split()
					if words[0] == '</tile>':
						self.lock.acquire()
						self.session.add(row)
						self.lock.release()
					while words[0] == '<primitive_site':
						row2 = self.FpgaTable()
						row2.model = row.model
						row2.version = row.version
						row2.speed = row.speed
						row2.x = row.x
						row2.y = row.y
						row2.genericType = row.genericType
						row2.tileX = row.tileX
						row2.tileY = row.tileY
						row2.specificType = row.specificType
						row2.num = row.num
						obj = re.match(r"(.+)_X([0-9]+)Y([0-9]+)", words[1].split('"')[1])
						if obj:
							row2.primGenType = obj.group(1)
							row2.primX = obj.group(2)
							row2.primY = obj.group(3)
						else:
							row2.primGenType = words[1].split('"')[1]
						row2.primSpecType = words[2].split('"')[1]
						row2.attr = words[3].split('"')[1]
						row2.primNum = words[4].split('"')[1]
						self.lock.acquire()
						self.session.add(row2)
						self.lock.release()
						line = self.fd.readline()
						if not line:
							return
						words = line.split()

	def __loadTable(self):
		self.FpgaTable = type('FpgaTable',(self.Base,),{'__table__': Table('fpga', self.Base.metadata, autoload=True, autoload_with=self.engine)})
		self.Base.metadata.create_all()

	def __initTable(self):
		self.FpgaTable = type('FpgaTable',(self.Base,),{'__tablename__':'fpga','id':Column(Integer,primary_key=True),'model':Column(String),'version':Column(String),'speed':Column(String),'x':Column(Integer),'y':Column(Integer),'genericType':Column(String),'tileX':Column(Integer),'tileY':Column(Integer),'specificType':Column(String),'dim':Column(Integer),'num':Column(Integer),'primGenType':Column(String),'primX':Column(Integer),'primY':Column(Integer),'primSpecType':Column(String),'attr':Column(String),'primNum':Column(Integer)})
		self.Base.metadata.create_all()

	def __initSession(self):
		self.Base = declarative_base()
		self.engine = create_engine("sqlite:///" + self.dbName)
		self.Base.metadata.bind = self.engine
		self.Session = sessionmaker(bind=self.engine)
		self.session = self.Session()

	def __init__(self):
		pass

	def __addBoard(self, speed=1):
		# generate xdlrc
		if (not os.path.exists(self.xmlFilename)):
			if (not os.path.exists(self.xdlrcName)):
				os.system("xdl -report " + self.fpgaName)
				os.system("mv *.xdlrc inputs/")
			os.system("python scripts/xdlrc2xml.py inputs/" + self.fpgaName + ".xdlrc")
		self.fd = open(self.xmlFilename, "r")
		self.lock = Lock()
		t = Thread(target=self.__xml2db)
		t.start()
		while t.isAlive():
			time.sleep(speed)
			self.lock.acquire()
			self.session.commit()
			self.lock.release()
		self.lock.acquire()
		self.session.commit()
		self.lock.release()
		self.fd.close()

	def __checkBoard(self):
		if len(self.session.query(self.FpgaTable).filter(self.FpgaTable.model==self.fpgaModel, self.FpgaTable.version==self.fpgaVersion, self.FpgaTable.speed==self.fpgaSpeed).all()) != 0:
			return True
		else:
			return False

	def __fixFpgaName(self):
		if (not os.path.exists(self.boards_PARSED_name)):
			if (not os.path.exists(self.boards_name)):
				os.system("partgen -i > " + self.boards_name)
			os.system("python scripts/parser_boards.py " + self.boards_name)
		fd = open(self.boards_PARSED_name, "r")
		while 1:
			line = fd.readline()
			if not line:
				break
			words = line.split()
			if self.fpgaName == ('').join(words) or self.fpgaName == words[0]:
				self.fpgaModel = words[0]
				self.fpgaVersion = words[1]
				self.fpgaSpeed = words[2]
				self.fpgaName = ('').join(words)
				break
		fd.close()
		self.xdlrcName = "inputs/" + self.fpgaName + ".xdlrc"
		self.xmlFilename = "inputs/" + self.fpgaName + ".xml"

	def loadFpga(self, fpgaName):
		self.fpgaName = fpgaName
		self.dbName = "fpgaDbs/fpgaDb.db"
		self.boards_name = "inputs/boards"
		self.boards_PARSED_name = "inputs/boards_PARSED.txt"
		if (not os.path.exists(self.dbName)):
			self.dbEmpty = True
			f = open(self.dbName, "w")
			f.close()
		else:
			self.dbEmpty = False
		self.__initSession()
		if self.dbEmpty:
			self.__initTable()
		else:
			self.__loadTable()
		self.__fixFpgaName()
		if self.__checkBoard():
			print "Board already exists"
		else:
			self.__addBoard()


