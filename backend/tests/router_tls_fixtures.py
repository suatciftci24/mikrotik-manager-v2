"""Synthetic RouterOS wire fixtures shared by transport tests; no IO."""
DER=b'SYNTHETIC_PUBLIC_CERT_NOT_A_REAL_CERT'
def sentence(*words):
    # Independent short-word fixtures from the published RouterOS framing format.
    result=b''
    for word in words:
        data=word.encode() if isinstance(word,str) else word;size=len(data)
        result+=(bytes([size]) if size<128 else bytes([0x80+(size>>8),size&255]))+data
    return result+b'\0'
def response(menu='fixture-interface',identity='CEBECI_TOWERS',model='RB3011UiAS',version='6.49.19',last=None):
    return sentence('!done')+sentence('!re','=name='+identity)+sentence('!done')+sentence('!re','=board-name='+model,'=version='+version)+sentence('!done')+(last if last is not None else sentence('!re','=name='+menu)+sentence('!done'))
class FakeTls:
    def __init__(self,data):self.data=data;self.sent=b'';self.closed=False;self.timeouts=[];self.peer=('10.250.0.19',8729);self.local=('10.250.0.1',55555);self.der=DER;self.san=(('IP Address','10.250.0.19'),)
    def recv(self,n):out=self.data[:min(n,3)];self.data=self.data[len(out):];return out
    def sendall(self,data):self.sent+=data
    def settimeout(self,t):self.timeouts.append(t)
    def close(self):self.closed=True
    def getpeername(self):return self.peer
    def getsockname(self):return self.local
    def getpeercert(self,binary_form=False):return self.der if binary_form else {'subjectAltName':self.san}
    def version(self):return 'TLSv1.2'
