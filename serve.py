from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import re, os
ROOT=Path(__file__).resolve().parent
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kw): super().__init__(*args,directory=str(ROOT),**kw)
    def send_head(self):
        self.byte_range=None
        path=self.translate_path(self.path)
        header=self.headers.get('Range')
        if header and os.path.isfile(path):
            size=os.path.getsize(path);match=re.fullmatch(r'bytes=(\d+)-(\d*)',header)
            if match:
                start=int(match[1]);end=min(int(match[2]) if match[2] else size-1,size-1)
                if start>=size or end<start:
                    self.send_error(416);return None
                f=open(path,'rb');f.seek(start);self.byte_range=(start,end)
                self.send_response(206);self.send_header('Content-type',self.guess_type(path));self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('Content-Range',f'bytes {start}-{end}/{size}');self.end_headers();return f
        return super().send_head()
    def copyfile(self,source,output):
        if self.byte_range:
            remaining=self.byte_range[1]-self.byte_range[0]+1
            while remaining>0:
                b=source.read(min(65536,remaining))
                if not b:break
                output.write(b);remaining-=len(b)
        else: super().copyfile(source,output)
    def log_message(self,*args):pass
    def handle(self):
        try: super().handle()
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Serve local review pages and seekable video.')
    parser.add_argument('--port', type=int, default=8672)
    parser.add_argument('--directory', type=Path, default=ROOT)
    options = parser.parse_args()
    ROOT = options.directory.resolve(strict=True)
    print(f'Match review: http://127.0.0.1:{options.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', options.port), Handler).serve_forever()
