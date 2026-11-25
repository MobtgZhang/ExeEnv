"""Readable figures regenerated from the newly computed audit tables."""
from .io import read_csv

NAMES={'direct':'Direct','draft':'Draft','self_refine':'Self-Refine','critic':'CRITIC','cove':'CoVe','sc':'SC','usc':'USC','cisc':'CISC','cure_l':'CURE','target_only':'Target-only'}
COLORS=['#0072B2','#E69F00','#999999','#CC79A7']


def generate(root, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'pdf.fonttype':42,'svg.hashsalt':'cure-audit-v1','figure.dpi':150})
    folder=output/'figures'
    folder.mkdir(exist_ok=True)
    def save(fig,name):
        fig.savefig(folder/(name+'.pdf'),bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None})
        fig.savefig(folder/(name+'.png'),bbox_inches='tight')
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,4.5))
    ax.set(xlim=(0,12.5),ylim=(0,5));ax.axis('off')
    def box(x,y,text,color,width=2.2):
        ax.add_patch(FancyBboxPatch((x,y),width,.75,boxstyle='round,pad=.08',facecolor=color,edgecolor='#333333'))
        ax.text(x+width/2,y+.375,text,ha='center',va='center',fontsize=9)
    def arrow(start,end,label=None,offset=(0,0)):
        ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'->','color':'#333333'})
        if label:
            ax.text((start[0]+end[0])/2+offset[0],(start[1]+end[1])/2+offset[1],label,ha='center',fontsize=8)
    box(.2,2.6,'Public task\nquestion + evidence','#D6EAF8')
    box(3.2,3.5,'Draft answer','#D5F5E3')
    box(3.2,1.8,'Condition ledger','#D5F5E3')
    box(6.3,1.8,'Independent checker','#D5F5E3')
    box(9.6,3.5,'Finalization / routing\nanswer or unavailable','#FDEBD0')
    arrow((2.5,3.1),(3.1,3.875))
    arrow((2.5,2.8),(3.1,2.175))
    arrow((5.5,2.175),(6.2,2.175))
    arrow((5.5,3.875),(9.5,3.875),'draft candidate',(0,.12))
    arrow((8.6,2.175),(10.65,3.38),'candidate + observations',(.3,-.3))
    ax.text(5.8,1.35,'Ledger and checker withhold the draft; saved observations replace tool execution.',ha='center',fontsize=9)
    box(.2,.15,'Saved request identity\nretry + reported usage','#EEEEEE',3.6)
    box(4.4,.15,'Candidate / terminal joins\ncoverage + loss partition','#EEEEEE',3.6)
    box(8.6,.15,'Offline reference scoring\nlabels never enter prompts','#EEEEEE',3.6)
    ax.text(6.25,4.7,'Execution audit of a four-stage workflow',ha='center',fontsize=13,weight='bold')
    save(fig,'01_framework')
    scores=read_csv(output/'terminal_scores.csv')
    fig,ax=plt.subplots(figsize=(10,4.5))
    bottom=[0]*len(scores)
    for field,label,color in [('matches','Reference match',COLORS[0]),('nonempty_mismatch','Nonempty mismatch',COLORS[1]),('returned_empty','Returned empty',COLORS[2]),('unavailable','Unavailable',COLORS[3])]:
        values=[int(r[field]) for r in scores]
        ax.bar(range(len(scores)),values,bottom=bottom,label=label,color=color)
        bottom=[a+b for a,b in zip(bottom,values)]
    ax.set(xticks=range(len(scores)),xticklabels=[NAMES.get(r['method'],r['method']) for r in scores],ylabel='Questions (all attempts)',ylim=(0,125),title='Frozen 120-question primary cohort')
    ax.tick_params(axis='x',rotation=35);ax.legend(ncol=2,loc='upper center',bbox_to_anchor=(.5,1.27))
    save(fig,'02_terminal_outcomes')
    parts=read_csv(output/'primary_partition.csv');r=next(r for r in parts if r['method']=='cure_l' and r['family']=='all')
    values=[int(r['draft']),int(r['repair']),-int(r['wrong_regression']),-int(r['empty_loss']),-int(r['delivery_loss']),int(r['final'])]
    fig,ax=plt.subplots(figsize=(8,4))
    current=0
    for i,v in enumerate(values):
        start=0 if i in (0,5) else min(current,current+v)
        ax.bar(i,abs(v),bottom=start,color=COLORS[0] if i in (0,5) else '#009E73' if v>0 else '#D55E00')
        ax.text(i,start+abs(v)+1,str(v) if i in (0,5) else f'{v:+}',ha='center')
        current=v if i==0 else current+v
    ax.set(xticks=range(6),xticklabels=['Draft','Repairs','Nonempty\nloss','Empty\nloss','Delivery\nloss','Final'],ylim=(0,105),ylabel='Reference matches',title='CURE: disjoint transition accounting')
    save(fig,'03_revision_partition')
    rows=read_csv(output/'shared_pool.csv')
    fig,ax=plt.subplots(figsize=(7,4))
    for offset,field,label,color in [(-.25,'pool_coverage','Matching candidate in pool',COLORS[0]),(0,'correct','Delivered match',COLORS[1]),(.25,'covered_without_selection','Covered but unavailable',COLORS[3])]:
        ax.bar([i+offset for i in range(3)],[int(r[field]) for r in rows],width=.24,label=label,color=color)
    ax.set(xticks=range(3),xticklabels=[NAMES[r['method']] for r in rows],ylim=(0,120),ylabel='Questions',title='Shared candidate pools (111 returned pools)');ax.legend(fontsize=8)
    save(fig,'04_candidate_selection')
    rows=read_csv(output/'replay.csv')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(10,4))
    names=[r['policy'].replace('agreement_fallback','Both').capitalize() for r in rows]
    ax.bar(names,[int(r['correct']) for r in rows],color=COLORS);ax.set(ylabel='Reference matches / 120',ylim=(0,120),title='Saved-response policy replay')
    bx.bar(names,[int(r['tokens'])/1e6 for r in rows],color=COLORS);bx.set(ylabel='Logical reported tokens (millions)',title='Consumed saved responses')
    for axis in (ax,bx):axis.tick_params(axis='x',rotation=20)
    save(fig,'05_policy_replay')
    curves=read_csv(output/'fault_curves.csv')
    fig,axes=plt.subplots(1,2,figsize=(10,4),sharey=True)
    for ax,dep in zip(axes,('independent','common')):
        for policy,color in zip(('original','agreement','fallback','both'),COLORS):
            rows=sorted([r for r in curves if r['cohort']=='extension' and r['dependence']==dep],key=lambda r:float(r['p']))
            rows=[r for r in rows if r['policy']==policy and float(r['p'])<=.4]
            ax.plot([float(r['p']) for r in rows],[float(r['expected_correct']) for r in rows],marker='o',label=policy,color=color)
        ax.set(xlabel='Injected marginal stage loss probability',title=dep.capitalize()+' stage loss',ylim=(0,105));ax.legend(fontsize=8)
    axes[0].set_ylabel('Expected matches on 101 completed trajectories')
    save(fig,'06_fault_sensitivity')
    rows=read_csv(output/'temporal_summary.csv')
    fig,ax=plt.subplots(figsize=(8,4))
    groups=sorted({r['block'] for r in rows})
    arms=sorted({r['arm'] for r in rows})
    for offset,arm,color in zip((-.18,.18),arms,COLORS):
        armrows=[next(r for r in rows if r['block']==b and r['arm']==arm) for b in groups]
        ax.bar([i+offset for i in range(len(groups))],[int(r['correct']) for r in armrows],width=.35,label=arm.replace('_',' '),color=color)
    ax.set(xticks=range(len(groups)),xticklabels=['Block '+b for b in groups],ylabel='Reference matches / 24 per arm',ylim=(0,26),title='Fresh executions: reused tasks, distinct schedule blocks');ax.legend()
    save(fig,'07_temporal_replication')
    rows=read_csv(output/'panel_cases_summary.csv')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(10,4))
    ax.bar([r['label'] for r in rows],[int(r['n']) for r in rows],color=COLORS[:len(rows)])
    ax.set(ylabel='Cases (balanced sample of 24)',title='Non-generator panel sufficiency votes')
    conditions=read_csv(output/'panel_conditions_summary.csv')
    labels=['entailment','applicability','relevance'];positive={'entailed','applicable','relevant'}
    for i,d in enumerate(labels):
        g=[r for r in conditions if r['dimension']==d]
        pos=sum(int(r['n']) for r in g if r['label'] in positive)
        bx.bar(i,pos,color=COLORS[0]);bx.bar(i,80-pos,bottom=pos,color=COLORS[2])
    bx.set(xticks=range(3),xticklabels=labels,ylabel='Conditions (80)',title='Positive votes and other votes')
    fig.suptitle('Automated judgments; no independent expert certification',fontsize=10)
    save(fig,'08_semantic_panel')
