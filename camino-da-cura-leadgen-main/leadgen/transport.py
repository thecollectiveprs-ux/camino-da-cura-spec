"""Direct HTTP transport: public-IP pinning, TLS hostname verification, no proxies/redirects."""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit
from urllib.error import HTTPError

class Response:
    def __init__(self,response,connection,url):
        self.response,self.connection,self.url=response,connection,url
        self.headers=response.headers
    def geturl(self): return self.url
    def read(self,size): return self.response.read(size)
    def __enter__(self): return self
    def __exit__(self,*args): self.response.close(); self.connection.close()

def public_open(request,timeout=15):
    url=request.full_url; p=urlsplit(url)
    port=p.port or (443 if p.scheme=='https' else 80)
    addresses=socket.getaddrinfo(p.hostname,port,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise OSError('Unsafe network destination')
    address=addresses[0][4][0]
    connection=http.client.HTTPSConnection(p.hostname,port,timeout=timeout) if p.scheme=='https' else http.client.HTTPConnection(p.hostname,port,timeout=timeout)
    # Connect to the validated numeric address; DNS is never resolved a second time.
    sock=socket.create_connection((address,port),timeout=timeout)
    if p.scheme=='https':
        try: sock=ssl.create_default_context().wrap_socket(sock,server_hostname=p.hostname)
        except Exception: sock.close(); raise
    connection.sock=sock
    try:
        target=(p.path or '/')+('?' + p.query if p.query else '')
        connection.request('GET',target,headers=dict(request.header_items()))
        response=connection.getresponse()
        if response.status>=300:
            status,headers=response.status,response.headers
            response.close(); connection.close()
            raise HTTPError(url,status,'HTTP response',headers,None)
        return Response(response,connection,url)
    except Exception:
        connection.close(); raise
