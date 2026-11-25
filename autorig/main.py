import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk
from psd_tools import PSDImage
import numpy as np,cv2,math,re,json,time,threading,queue
class App:
 def __init__(self,r):
  self.r=r;r.title("Lussal AutoRig Studio v0.2 - Performance Preview");r.geometry("1100x720");r.configure(bg="#111827");self.layers=[];self.size=(1,1);self.path=None;self.pending=None;self.busy=False;self.jobs=queue.Queue();self.r.after(50,self.poll)
  s=ttk.Style();s.theme_use("clam");s.configure(".",background="#202c40",foreground="#e5efff",fieldbackground="#172235")
  b=ttk.Frame(r);b.pack(fill="x")
  for name,fn in [("Import PSD",self.load),("Auto Mesh",self.rig),("Save Project",self.save),("Open Project",self.open),("Export PNG",self.export)]:ttk.Button(b,text=name,command=fn).pack(side="left",padx=4,pady=5)
  self.mesh=tk.BooleanVar();ttk.Checkbutton(b,text="Mesh",variable=self.mesh,command=self.draw).pack(side="left")
  p=ttk.Panedwindow(r,orient="horizontal");p.pack(fill="both",expand=True)
  self.tree=ttk.Treeview(p,columns=("kind",),show="tree headings");self.tree.heading("#0",text="Layer");self.tree.heading("kind",text="Type");p.add(self.tree,weight=1)
  self.canvas=tk.Canvas(p,bg="#101a2a");p.add(self.canvas,weight=5);self.canvas.bind("<Configure>",lambda e:self.schedule())
  side=ttk.Frame(p);p.add(side,weight=1);self.vars={}
  for k,lo,hi,v in [("Head X",-30,30,0),("Head Y",-30,30,0),("Head Z",-30,30,0),("Eye",0,1,1),("Mouth",0,1,0),("Body",-30,30,0),("Breath",0,1,0)]:
   self.vars[k]=tk.DoubleVar(value=v);ttk.Label(side,text=k).pack();ttk.Scale(side,from_=lo,to=hi,variable=self.vars[k],command=lambda _:self.schedule()).pack(fill="x",pady=8)
  self.kind=tk.StringVar();c=ttk.Combobox(side,textvariable=self.kind,values=["head","hair","eye","mouth","body","unknown"],state="readonly");c.pack();c.bind("<<ComboboxSelected>>",self.change);self.tree.bind("<<TreeviewSelect>>",self.select)
  self.status=tk.StringVar(value="Prototype: CMO3/MOC3 export unavailable");ttk.Label(r,textvariable=self.status).pack(fill="x")
 def select(self,e):
  if self.tree.selection():self.kind.set(self.layers[int(self.tree.selection()[0])]["kind"])
 def change(self,e):
  if self.tree.selection():
   i=int(self.tree.selection()[0]);self.layers[i]["kind"]=self.kind.get();self.tree.set(str(i),"kind",self.kind.get());self.draw()
 def load(self):
  p=filedialog.askopenfilename(filetypes=[("PSD","*.psd")])
  if p:
   self.read_async(p)
 def schedule(self):
  if self.pending is not None:self.r.after_cancel(self.pending)
  self.pending=self.r.after(35,self.flush)
 def flush(self):
  self.pending=None;self.draw()
 def read_async(self,p):
  if self.busy:return
  self.busy=True;self.status.set("Loading PSD in background...")
  def work():
   try:self.jobs.put(("ok",p,self.decode(p)))
   except Exception as e:self.jobs.put(("error",p,str(e)))
  threading.Thread(target=work,daemon=True).start()
 def poll(self):
  try:
   tag,p,data=self.jobs.get_nowait();self.busy=False
   if tag=="ok":self.install(p,data)
   else:messagebox.showerror("Import",data);self.status.set("Import failed")
  except queue.Empty:pass
  finally:self.r.after(50,self.poll)
 def decode(self,p):
  d=PSDImage.open(p);layers=[];scale=min(1,1000/max(d.size))
  for l in reversed(list(d.descendants())):
   if l.is_group() or not l.is_visible():continue
   im=l.topil()
   if im is None or not im.width or not im.height:continue
   k=next((k for k,pat in [("eye","eye|mata"),("mouth","mouth|lip|mulut"),("hair","hair|rambut"),("head","head|face|nose|brow|mask|topeng"),("body","body|arm|cloth")] if re.search(pat,l.name,re.I)),"unknown")
   im=im.convert("RGBA");preview=im.resize((max(1,round(im.width*scale)),max(1,round(im.height*scale))),Image.Resampling.BILINEAR)
   layers.append(dict(name=l.name,kind=k,im=im,preview=preview,xy=(l.left,l.top),mesh=[]))
  return d.size,layers
 def install(self,p,data):
  self.path=p;self.size,self.layers=data;self.tree.delete(*self.tree.get_children())
  for i,l in enumerate(self.layers):self.tree.insert("","end",iid=str(i),text=l["name"],values=(l["kind"],))
  self.status.set(str(len(self.layers))+" layers loaded | Preview optimized | CMO3 unavailable");self.draw()
 def read(self,p):
  self.install(p,self.decode(p))
 def rig(self):
  try:
   for l in self.layers:
    a=np.asarray(l["im"])[:,:,3];h,w=a.shape;step=max(4,max(w,h)//18);pts={(x,y) for y in range(0,h,step) for x in range(0,w,step) if a[y,x]>10}
    cs,_=cv2.findContours((a>10).astype("uint8"),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    for c in cs:pts.update(tuple(map(int,p[0])) for p in cv2.approxPolyDP(c,max(1,step/3),True))
    sub=cv2.Subdiv2D((0,0,w,h))
    for x,y in pts:sub.insert((float(x),float(y)))
    l["mesh"]=[]
    for t in sub.getTriangleList():
     q=np.array(t).reshape(3,2);x,y=q.mean(0).astype(int)
     if 0<=x<w and 0<=y<h and a[y,x]>10:l["mesh"].append(q.tolist())
   self.status.set("Mesh triangles: "+str(sum(len(l["mesh"]) for l in self.layers)));self.draw()
  except Exception as e:messagebox.showerror("Mesh",str(e))
 def render(self,sc):
  W,H=self.size;ow,oh=max(1,int(W*sc)),max(1,int(H*sc));out=np.zeros((oh,ow,4),np.float32);lines=[];p={k:v.get() for k,v in self.vars.items()}
  for l in self.layers:
   im=l["im"];k=l["kind"];x,y=l["xy"];a=dx=dy=0;sx=sy=1
   if k in ("head","hair","eye","mouth"):a=p["Head Z"];dx=p["Head X"]*W/450;dy=p["Head Y"]*H/550;sx=1-abs(p["Head X"])/250
   if k=="eye":sy=max(.07,p["Eye"])
   if k=="mouth":sy=1+p["Mouth"]*.9
   if k=="body":a=p["Body"]*.5;sy=1+p["Breath"]*.025
   rad=math.radians(a);R=np.array([[math.cos(rad),-math.sin(rad)],[math.sin(rad),math.cos(rad)]]);A=R@np.diag([sx,sy]);local=np.array([im.width/2,im.height/2]);center=np.array([W*.5,H*.3]);b=R@(np.array([x,y])+local-center)+center-A@local+np.array([dx,dy]);M=np.column_stack((A,b))*sc
   src=l["preview"] if sc<.99 else im
   T=M.copy();T[:,0]*=im.width/src.width;T[:,1]*=im.height/src.height
   corners=np.array([[0,0],[src.width,0],[0,src.height],[src.width,src.height]])@T[:,:2].T+T[:,2]
   x0,y0=np.maximum(0,np.floor(corners.min(0)).astype(int));x1,y1=np.minimum([ow,oh],np.ceil(corners.max(0)).astype(int))
   if x1>x0 and y1>y0:
    T[:,2]-=[x0,y0];arr=np.asarray(src,dtype=np.float32)/255;arr[:,:,:3]*=arr[:,:,3:4];warp=cv2.warpAffine(arr,T,(int(x1-x0),int(y1-y0)));roi=out[y0:y1,x0:x1];roi[:]=warp+roi*(1-warp[:,:,3:4])
   if self.mesh.get():lines.extend(np.array(t)@M[:,:2].T+M[:,2] for t in l["mesh"])
  out[:,:,:3]/=np.maximum(out[:,:,3:4],1e-6);return Image.fromarray(np.uint8(np.clip(out,0,1)*255),"RGBA"),lines
 def draw(self):
  if not self.layers:return
  w,h=self.canvas.winfo_width(),self.canvas.winfo_height();im,lines=self.render(max(.001,min(w/self.size[0],h/self.size[1])*.92));self.photo=ImageTk.PhotoImage(im);self.canvas.delete("all");x,y=(w-im.width)/2,(h-im.height)/2;self.canvas.create_image(x,y,image=self.photo,anchor="nw")
  for t in lines:self.canvas.create_polygon(*((t+[x,y]).flatten()),outline="#43d9ef",fill="")
 def save(self):
  if not self.path:return
  p=filedialog.asksaveasfilename(defaultextension=".lar")
  if p:
   with open(p,"w",encoding="utf8") as f:json.dump(dict(psd=self.path,layers=[{k:l[k] for k in ("name","kind","mesh")} for l in self.layers],params={k:v.get() for k,v in self.vars.items()}),f)
 def open(self):
  p=filedialog.askopenfilename(filetypes=[("Project","*.lar")])
  if p:
   try:
    with open(p,encoding="utf8") as f:d=json.load(f)
    self.read(d["psd"])
    for i,(l,s) in enumerate(zip(self.layers,d["layers"])):
     if l["name"]==s["name"]:l.update(kind=s["kind"],mesh=s["mesh"]);self.tree.set(str(i),"kind",l["kind"])
    for k,v in d["params"].items():self.vars[k].set(v)
    self.draw()
   except Exception as e:messagebox.showerror("Project",str(e))
 def export(self):
  if not self.layers:return
  p=filedialog.asksaveasfilename(defaultextension=".png")
  if p:self.render(1)[0].save(p)
if __name__=="__main__":
 r=tk.Tk();App(r);r.mainloop()
