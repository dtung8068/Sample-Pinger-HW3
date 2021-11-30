import os
import sys
import struct
import time
import select
import socket
import binascii

ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY= 0

def checksum(str):
    csum = 0
    countTo = (len(str) / 2) * 2

    count = 0
    while count < countTo:
        thisVal = str[count+1] * 256 + str[count]
        csum = csum + thisVal
        csum = csum & 0xffffffff
        count = count + 2

    if countTo < len(str):
        csum = csum + str[len(str) - 1]
        csum = csum & 0xffffffff

    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer

def receiveOnePing(mySocket, ID, timeout, destAddr):
    global rtt_min, rtt_max, rtt_sum, rtt_cnt
    timeLeft = timeout
    while 1:
        startedSelect = time.time()
        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = (time.time() - startedSelect)
        if whatReady[0] == []: # Timeout
            return "Request timed out."
        recPacket, addr = mySocket.recvfrom(1024)
        timeReceived = time.time() #After receiving packet. 
        #Fill in start

        #Fetch the ICMP header from the IP packet
        header = recPacket[20:28] #ICMP Header: bytes 20-28
        header = struct.unpack("bbHHh", header)
        #print(header) To check that header matches reply. 
        #Fill in end
        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return "Request timed out." 
        else:
            rtt_cnt += 1
            rtt_time = (timeReceived - startedSelect) * 1000 #Multiply by 1000 to get ms.
            rtt_sum += rtt_time #For average calculation
            if(rtt_time > rtt_max):
                rtt_max = rtt_time #Update max rtt time when greater.
            if(rtt_time < rtt_min):
                rtt_min = rtt_time #Update min rtt time when smaller.
            if(rtt_time < 1):
                rtt_time = '<1' #For display purposes. 
            else:
                rtt_time = '{:.0f}'.format(rtt_time) #Also for display purposes. 
            timeLeft = '{:.0f}'.format(timeLeft * 1000)
            additionalInfo = 'Additional Info: Type={}, Code={}, Checksum={}, ID={}, Sequence={}'.format(header[0], header[1], header[2], header[3], header[4])
            return ('Reply from {}: bytes={} time={}ms TTL={}\n'.format(destAddr, struct.calcsize("bbHHh"), rtt_time, timeLeft) + additionalInfo)

def sendOnePing(mySocket, destAddr, ID):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)

    myChecksum = 0
    # Make a dummy header with a 0 checksum.
    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", time.time())
    # Calculate the checksum on the data and the dummy header.
    myChecksum = checksum(header + data)
    # Get the right checksum, and put in the header
    if sys.platform == 'darwin':
        myChecksum = socket.htons(myChecksum) & 0xffff
        #Convert 16-bit integers from host to network byte order.
    else:
        myChecksum = socket.htons(myChecksum)
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data

    mySocket.sendto(packet, (destAddr, 1)) # AF_INET address must be tuple, not str
    #Both LISTS and TUPLES consist of a number of objects
    #which can be referenced by their position number within the object

def doOnePing(destAddr, timeout):
    icmp = socket.getprotobyname("icmp")
    #SOCK_RAW is a powerful socket type. For more details see: http://sock-raw.org/papers/sock_raw
    try:
        mySocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
    except socket.error:
        print('Socket could not be created. Exiting now.')
        sys.exit()

    myID = os.getpid() & 0xFFFF #Return the current process i
    sendOnePing(mySocket, destAddr, myID)
    delay = receiveOnePing(mySocket, myID, timeout, destAddr)
    mySocket.close()
    return delay

def ping(host, timeout=1):
    counter = 4 #Number of times to ping. 
    global rtt_min, rtt_max, rtt_sum, rtt_cnt
    rtt_min = float('+inf')
    rtt_max = float('-inf')
    rtt_sum = 0
    rtt_cnt = 0
    cnt = 0
    #timeout=1 means: If one second goes by without a reply from the server,
    #the client assumes that either the client's ping or the server's pong is lost
    try:
        dest = socket.gethostbyname(host)
    except socket.gaierror:
        print('Ping request could not find host {}. Please check the name and try again.'.format(host))
        sys.exit()
    if(host == dest):
        print("Pinging " + dest + ' with ' + str(struct.calcsize('bbHHh')) + ' bytes of data:')
    else:
        print("Pinging {} [{}] with {} bytes of data:".format(host, dest, struct.calcsize('bbHHh')))
    #Send ping requests to a server separated by approximately one second
    try:
        while counter != 0:
            cnt += 1
            print(doOnePing(dest, timeout))
            time.sleep(1)
            counter += -1
        if cnt != 0:
            print('Ping statistics for {}:'.format(host))
            print('\tPackets: Sent = {}, Received = {}, Lost = {} ({:.0f}% loss),'.format(cnt, rtt_cnt, cnt - rtt_cnt, 100.0 - rtt_cnt * 100.0 / cnt))
            if rtt_cnt != 0:
                print('Approximate round trip times in milli-seconds:')
                print ('\tMinimum = {:.0f}ms, Maximum = {:.0f}ms, Average = {:.0f}ms'.format(rtt_min, rtt_max, rtt_sum / rtt_cnt))
    except KeyboardInterrupt:
        if cnt != 0:
            print('Ping statistics for {}:'.format(host))
            print('\tPackets: Sent = {}, Received = {}, Lost = {} ({:.0f}% loss),'.format(cnt, rtt_cnt, cnt - rtt_cnt, 100.0 - rtt_cnt * 100.0 / cnt))
            if rtt_cnt != 0:
                print('Approximate round trip times in milli-seconds:')
                print ('\tMinimum = {:.0f}ms, Maximum = {:.0f}ms, Average = {:.0f}ms'.format(rtt_min, rtt_max, rtt_sum / rtt_cnt))

ping(sys.argv[1])