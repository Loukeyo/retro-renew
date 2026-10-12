"""Windows GUI, also runnable from source on Python with Tk support."""
import json, os, queue, subprocess, sys, threading, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core import load_recipe, preflight, install, restore, SafetyError, target, no_links

BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))

class App:
    def __init__(self, recipe):
        self.recipe=recipe; self.events=queue.Queue(); self.busy=False; self.archives=[]; self.messages=[]
        self.root=tk.Tk(); self.root.title('Retro Renew | '+recipe['title']); self.root.geometry('800x680'); self.root.minsize(680,580)
        self.root.configure(bg='#11171c'); self.root.protocol('WM_DELETE_WINDOW',self.close)
        style=ttk.Style(); style.theme_use('clam')
        style.configure('.',background='#11171c',foreground='#e8ece8',font=('Segoe UI',10))
        style.configure('TButton',padding=10,background='#28353b',foreground='#f4f6f3')
        style.map('TButton',background=[('active','#3b4a50')],foreground=[('disabled','#758187')])
        style.configure('Accent.TButton',background='#b9f269',foreground='#11171c')
        style.configure('TEntry',fieldbackground='#202a30',foreground='#f4f6f3',padding=8)
        outer=ttk.Frame(self.root,padding=26); outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='RETRO / RENEW',font=('Segoe UI',13,'bold'),foreground='#b9f269').pack(anchor='w')
        ttk.Label(outer,text=recipe['title'],font=('Segoe UI',23,'bold')).pack(anchor='w',pady=(18,4))
        ttk.Label(outer,text=f"Setup {recipe['version']}  /  {recipe['edition']}").pack(anchor='w')
        if recipe['status']=='demo':
            ttk.Label(outer,text='TRAINING DEMO: use the generated demo folder. This does not mod a real game.',foreground='#e9bf72',wraplength=700).pack(anchor='w',pady=12)
        ttk.Label(outer,text='1  Choose the game folder',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(20,8))
        row=ttk.Frame(outer); row.pack(fill='x')
        self.folder=tk.StringVar(); self.entry=ttk.Entry(row,textvariable=self.folder); self.entry.pack(side='left',fill='x',expand=True)
        self.buttons=[]
        self.button(row,'Browse',self.browse).pack(side='left',padx=(8,0))
        self.button(outer,'Find Steam installation',self.detect).pack(anchor='w',pady=8)
        ttk.Label(outer,text='2  Add the tested mod archives',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(12,8))
        row=ttk.Frame(outer); row.pack(fill='x')
        self.button(row,'Add ZIP files',self.add).pack(side='left')
        self.button(row,'Use Downloads folder',self.downloads).pack(side='left',padx=8)
        self.button(row,'Mods & author links',self.credits).pack(side='left')
        self.archive_label=ttk.Label(outer,text='No archives selected. Direct downloads, if approved, happen during installation.')
        self.archive_label.pack(anchor='w',pady=8)
        self.consent=tk.BooleanVar()
        self.check=ttk.Checkbutton(outer,text='I reviewed the mods and author notices, closed the game, and want this tested setup.',variable=self.consent)
        self.check.pack(anchor='w',pady=12)
        row=ttk.Frame(outer); row.pack(fill='x')
        self.button(row,'Check installation',lambda:self.run('check')).pack(side='left')
        self.button(row,'Install setup',lambda:self.run('install'),style='Accent.TButton').pack(side='left',padx=8)
        self.button(row,'Restore / recover',lambda:self.run('restore')).pack(side='left')
        self.progress=ttk.Progressbar(outer,mode='indeterminate'); self.progress.pack(fill='x',pady=(16,8))
        self.status=ttk.Label(outer,text='Ready. Checks must pass before any game file is replaced.',wraplength=700)
        self.status.pack(anchor='w',pady=(0,8))
        self.log=tk.Text(outer,height=7,bg='#0b1014',fg='#cbd5d1',insertbackground='#fff',font=('Consolas',9),state='disabled',relief='flat')
        self.log.pack(fill='both',expand=True)
        row=ttk.Frame(outer); row.pack(fill='x',pady=(12,0))
        self.button(row,'Play game',self.play).pack(side='left')
        self.button(row,'Export diagnostic log',self.export).pack(side='right')
        self.root.after(100,self.poll)

    def button(self,parent,text,command,**kwargs):
        b=ttk.Button(parent,text=text,command=command,**kwargs); self.buttons.append(b); return b
    def browse(self):
        p=filedialog.askdirectory(title='Choose the folder containing '+self.recipe['executable'])
        if p:self.folder.set(p)
    def detect(self):
        if os.name!='nt': messagebox.showinfo('Find game','Automatic Steam detection is available on Windows. Use Browse.'); return
        import winreg
        roots=[]
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as k:
                roots.append(Path(winreg.QueryValueEx(k,'SteamPath')[0]))
        except OSError: pass
        import re
        for r in list(roots):
            vdf=r/'steamapps'/'libraryfolders.vdf'
            if vdf.is_file():
                roots.extend(Path(p.replace('\\\\','\\')) for p in re.findall(r'"path"\s+"([^"]+)"',vdf.read_text(errors='replace')))
        matches=[]
        for r in roots:
            for sub in self.recipe.get('steam_folders',[]):
                p=r/'steamapps'/'common'/sub
                if (p/self.recipe['executable']).is_file() and p not in matches: matches.append(p)
        if len(matches)==1: self.folder.set(str(matches[0]))
        else: messagebox.showinfo('Find game','No unique supported installation found. Select the correct folder using Browse.')
    def add(self):
        self.archives=list(dict.fromkeys(self.archives+list(filedialog.askopenfilenames(filetypes=[('ZIP archives','*.zip')]))))
        self.archive_label.config(text=f'{len(self.archives)} archive(s) selected. Exact versions are checked by checksum.')
    def downloads(self):
        folder=Path.home()/'Downloads'
        if folder.is_dir():
            paths=sorted(folder.glob('*.zip'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]
            self.archives=list(dict.fromkeys(self.archives+[str(p) for p in paths]))
        self.archive_label.config(text=f'{len(self.archives)} archive(s) selected. Exact versions are checked by checksum.')
    def credits(self):
        w=tk.Toplevel(self.root); w.title('Mods & author notices'); w.geometry('740x550')
        box=ttk.Frame(w,padding=20); box.pack(fill='both',expand=True)
        for a in self.recipe['artifacts']:
            ttk.Label(box,text=a['name']+' by '+a['author'],font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(14,4))
            ttk.Label(box,text=a.get('notice','')+'\nPermission record: '+a['permission']['evidence'],wraplength=680).pack(anchor='w')
            ttk.Button(box,text='Open original project page',command=lambda u=a['page']:webbrowser.open(u)).pack(anchor='w',pady=6)
        ttk.Label(box,text='No third-party ownership is claimed. Use the exact files tested for this setup.',wraplength=680).pack(anchor='w',pady=20)
    def run(self,action):
        if self.busy:return
        if not self.folder.get(): messagebox.showinfo('Choose a game','Select your game folder first.'); return
        if action=='install' and not self.consent.get(): messagebox.showinfo('Review setup','Review the author notices and tick the confirmation before installing.'); return
        if action=='restore' and not messagebox.askyesno('Restore previous setup','Restore files changed by this setup? Files you changed afterwards will block automatic restoration.'):
            return
        root=self.folder.get(); archives=list(self.archives)
        self.busy=True; self.entry.state(['disabled']); self.check.state(['disabled'])
        for b in self.buttons:b.state(['disabled'])
        self.progress.start(); self.status.config(text='Working. Keep this window open.')
        def work():
            try:
                if action=='check': preflight(self.recipe,root); result='Game edition, conflicts, storage, and write access passed. Archives are verified during installation.'
                elif action=='install': install(self.recipe,root,archives,lambda m:self.events.put(('log',m))); result='Setup installed and verified. Your backups are retained in the game folder.'
                else: restore(self.recipe,root,lambda m:self.events.put(('log',m))); result='Previous files restored. Unrelated files and saves were preserved.'
                self.events.put(('done',result))
            except Exception as e:
                msg=str(e) if isinstance(e,SafetyError) else f'{type(e).__name__}: operation stopped. Check archives, permissions, and recovery status.'
                self.events.put(('error',msg))
        threading.Thread(target=work,daemon=False).start()
    def poll(self):
        try:
            while True:
                kind,msg=self.events.get_nowait(); self.messages.append(msg)
                self.log.config(state='normal'); self.log.insert('end',msg+'\n'); self.log.see('end'); self.log.config(state='disabled')
                if kind in ('done','error'):
                    self.busy=False; self.progress.stop(); self.entry.state(['!disabled']); self.check.state(['!disabled'])
                    for b in self.buttons:b.state(['!disabled'])
                    self.status.config(text=msg)
                    if kind=='error':messagebox.showerror('Operation stopped safely',msg)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def play(self):
        if self.recipe['status']=='demo':messagebox.showinfo('Training demo','The demo creates harmless text files, not a playable game.'); return
        try:
            root=no_links(self.folder.get()); jp=no_links(root/'.retro-renew'/'journal.json')
            j=json.loads(jp.read_text())
            if j.get('status')!='installed' or j.get('recipe')!=self.recipe['id'] or j.get('version')!=self.recipe['version']:
                raise SafetyError('Complete or recover this setup before launching.')
            from core import digest, not_running
            not_running(self.recipe)
            for m in self.recipe['markers']:
                if digest(target(root,m['path']))!=m['sha256']:raise SafetyError('The game executable changed. Launch blocked.')
            for e in j['entries']:
                if digest(target(root,e['path']))!=e['new']:raise SafetyError('An installed file changed. Launch from your store client or review your setup.')
            subprocess.Popen([str(target(root,self.recipe['executable']))],cwd=root)
        except Exception as e:messagebox.showerror('Cannot launch',str(e))
    def export(self):
        p=filedialog.asksaveasfilename(defaultextension='.txt',initialfile='retro-renew-diagnostics.txt')
        if p:
            text=f"Retro Renew 0.1\nSetup: {self.recipe['id']} / {self.recipe['version']}\nPlatform: {sys.platform}\n\n"+'\n'.join(self.messages)
            text=text.replace(str(Path.home()),'[user folder]')
            Path(p).write_text(text,encoding='utf-8')
    def close(self):
        if self.busy:messagebox.showinfo('Installation active','Wait for the operation to finish. If interrupted externally, use Restore / recover on the next run.'); return
        self.root.destroy()

if __name__=='__main__':
    try:
        path=Path(sys.argv[1]) if len(sys.argv)>1 and not getattr(sys,'frozen',False) else BASE/'recipe.json'
        app=App(load_recipe(path)); app.root.mainloop()
    except Exception as e:
        r=tk.Tk(); r.withdraw(); messagebox.showerror('Retro Renew could not start',str(e)); r.destroy(); sys.exit(1)
