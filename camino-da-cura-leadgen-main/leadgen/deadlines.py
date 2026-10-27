import logging
import multiprocessing
import time
log=logging.getLogger(__name__)
class DeadlineExceeded(TimeoutError): pass

def _worker(pipe,fn,args):
    try: pipe.send(('ok',fn(*args)))
    except Exception as exc: pipe.send(('error',exc))
    finally: pipe.close()

def bounded_call(fn,args,seconds,label):
    context=multiprocessing.get_context('spawn')
    receiver,sender=context.Pipe(duplex=False)
    process=context.Process(target=_worker,args=(sender,fn,args),daemon=True)
    process.start(); sender.close()
    deadline=time.monotonic()+seconds
    try:
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise DeadlineExceeded(label+' timed out after '+str(seconds)+' seconds')
            if receiver.poll(min(5,remaining)):
                try: status,result=receiver.recv()
                except EOFError: raise RuntimeError(label+' worker exited without a result') from None
                if status=='error': raise result
                return result
            log.info('Still waiting: %s (%.0fs remaining)',label,max(0,deadline-time.monotonic()))
    finally:
        if process.is_alive(): process.terminate()
        process.join(timeout=1)
        if process.is_alive(): process.kill(); process.join(timeout=1)
        receiver.close(); process.close()
