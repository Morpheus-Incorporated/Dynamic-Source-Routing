from socket import *
from random import *
from subprocess import *
from threading import *
from time import *



my_ip = input('Enter static ip to be used : ')
run(['ip', 'link', 'set', 'wlan0', 'down'])
run(['iwconfig', 'wlan0', 'mode', 'ad-hoc', 'channel', '8', 'essid', 'ADHOCNETWORK'])
run(['ip', 'link', 'set', 'wlan0', 'up'])
run(['ip', 'addr', 'add', my_ip + '/24', 'dev', 'wlan0'])


my_ip_b = inet_aton(my_ip)
my_ip_i = int.from_bytes(my_ip_b, 'big')



sck = socket(type = SOCK_DGRAM)
sck.bind(('', 1999))


sock = socket(type = SOCK_DGRAM)
sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

processed_packets = { ('0.0.0.0', 0) }
rreq_table = { ('0.0.0.0', time(), 0) }

def ui():
	global processed_packets
	global rreq_table
	while True:
		choice = input('>>> ')
		if choice == 'rreq':
			target_ip = input('Enter ip address to rreq : ')
			uid = randint(0, 2**32 - 1)
			packet = bytes('1', encoding='utf-8') + my_ip_b + uid.to_bytes(4, byteorder='big') + inet_aton(target_ip) + my_ip_b
			processed_packets = processed_packets | {(my_ip_i, uid)}
			rreq_table = rreq_table | {(target_ip, time(), uid)}
			sock.sendto(packet, ('192.168.11.255', 1999))
		elif choice == 'rerr':
			target_ip = input('Enter ip address that can\'t be reached : ')
			uid = randint(0, 2**32 - 1)
			packet = bytes('3', encoding='utf-8') + my_ip_b + uid.to_bytes(4, byteorder='big') + inet_aton(target_ip)
			sock.sendto(packet, ('192.168.11.255', 1999))



def route():
	global processed_packets
	routing_table = {}
	while True:
		msg = sck.recv(1024)
		print('received :', msg)
		if msg[0] == 49:	# RREQ
			src_ip = int.from_bytes(msg[1:5], 'big')
			uid = int.from_bytes(msg[5:9], 'big')
			dst_ip = int.from_bytes(msg[9:13], 'big')
			path = msg[13:]
			if (src_ip, uid) in processed_packets:
				continue
			else:
				processed_packets = processed_packets | {(src_ip, uid)}
				if dst_ip == my_ip_i or dst_ip in routing_table:
					reply_node = path[-4:]
					route_reply = bytes('2', encoding='utf-8') + my_ip_b + (randint(0, 2**32 - 1)).to_bytes(4, byteorder='big') + src_ip.to_bytes(4, byteorder='big') + path + inet_aton(my_ip)
					sock.sendto(route_reply, (inet_ntoa(reply_node), 1999))
				else:
					sock.sendto(msg + inet_aton(my_ip), ('192.168.11.255', 1999))
		elif msg[0] == 50:	# RREP
			src_ip = msg[1:5]
			uid = msg[5:9]
			dst_ip = msg[9:13]
			path = msg[13:]
			for i in range((len(msg) - 13) // 4):
				if path[i*4:i*4+4] == my_ip_b:
					break
			current_pos = i
			for j in range(current_pos):
				run(['ip', 'route', 'add', inet_ntoa(path[j*4:j*4+4]), 'via', inet_ntoa(path[(current_pos-1)*4:current_pos*4])])
			for i in range(i + 1, (len(msg) - 13) // 4):
				run(['ip', 'route', 'add', inet_ntoa(path[i*4:i*4+4]), 'via', inet_ntoa(path[(current_pos+1)*4:current_pos*4+8])])
			if my_ip_b == dst_ip:
				pass
			else:
				sock.sendto(msg, (inet_ntoa(path[current_pos*4-4:current_pos*4]), 1999))
		elif msg[0] == 51:	# RERR
			src_ip = msg[1:5]
			uid = msg[5:9]
			unreachable_ip = msg[9:13]
			op = run(['ip', 'route'], stdout=PIPE)
			flag = False
			for route in op.stdout.decode('utf-8').split('\n')[:-1]:
				if route.split(' ')[2] == inet_ntoa(src_ip) and route.split(' ')[0] == inet_ntoa(unreachable_ip):
					flag = True
					run(['ip', 'route', 'del', route.split(' ')[0]])
			if flag:
				sock.sendto(msg[0] + my_ip_b + msg[5:], ('192.168.11.255', 1999))



def timeout():
	global rreq_table
	global processed_packets
	while True:
		sleep(5)
		for entry in rreq_table:
			if time() - entry[1] > 5:
				print('Timeout occured for', entry[0])
				rreq_table = rreq_table - { entry }
				processed_packets = processed_packets - { (entry[0], entry[2]) }



t1 = Thread(target=ui)
t1.start()
t2 = Thread(target=route)
t2.start()
t3 = Thread(target=timeout)
t3.start()

