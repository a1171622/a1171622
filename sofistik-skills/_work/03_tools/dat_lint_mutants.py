g={'__name__':'lintmod'}; exec(open('/mnt/project-files/skills/_work/03_tools/dat_lint.py').read(),g); lint=g['lint']
base=open('/mnt/project-files/26016/audit/26016_loads_unified.dat',encoding='utf-8').read()
b=len(lint(base))
M={'hard-coded SDL':base.replace("AREA LAR '1' WIDE 0 TYPE PG #SDLF","AREA LAR '1' WIDE 0 TYPE PG 0.89",1),
   'operator in name':base.replace('STO#GQ     1.5','STO#GQ     1.5\nSTO#NDIV 8',1),
   'line 300 chars':base.replace('STO#GQ     1.5','STO#GQ     1.5 $'+'x'*290,1),
   'COPY undefined LC':base.replace('  COPY NO 81 FACT 1','  COPY NO 89 FACT 1',1),
   '26-item list':base.replace('STO#GQ     1.5','STO#GQ     1.5\nLC '+','.join(str(i) for i in range(101,127)),1)}
for k,t in M.items(): print('%-20s new findings: %d'%(k,len(lint(t))-b))
