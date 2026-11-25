"""Render the manuscript figures from the reconstructed tables."""
from shutil import copyfile

from .io import read_csv


ORDER = ('direct', 'draft', 'self_refine', 'sc', 'usc', 'cisc', 'cove', 'critic', 'target_only', 'cure_l')
LABELS = ('Direct', 'Shared draft', 'Self-Refine', 'SC', 'USC', 'CISC', 'CoVe', 'CRITIC', 'Target-only', 'CURE')
NAMES = dict(zip(ORDER, LABELS))


def generate_paper_figures(root, results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    folder = results/'paper-figures'
    folder.mkdir(exist_ok=True)
    copyfile(root/'figure-assets/audit-architecture.pdf', folder/'audit-architecture.pdf')

    def save(figure, name):
        figure.savefig(folder/(name + '.pdf'), bbox_inches='tight', metadata={'CreationDate': None, 'ModDate': None})
        plt.close(figure)

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'pdf.fonttype': 42,
                         'axes.spines.right': False, 'axes.spines.top': False})

    scores = {row['method']: row for row in read_csv(results/'primary_scores.csv')}
    pairs = {row['control']: row for row in read_csv(results/'paired.csv')}
    figure, (accuracy, paired, cost) = plt.subplots(1, 3, figsize=(7.16, 2.85), gridspec_kw={'width_ratios': [1.1, 1.2, 1]})
    for index, method in enumerate(ORDER):
        row = scores[method]
        rate, low, high = (100*float(row[key]) for key in ('accuracy', 'ci_low', 'ci_high'))
        color = '#147d73' if method == 'cure_l' else '#325f8a' if method == 'draft' else '#73879a'
        accuracy.errorbar(rate, index, xerr=[[rate-low], [high-rate]], fmt='o', markersize=3, capsize=2, color=color)
        usage = float(row['mean_tokens'])/1000
        cost.scatter(usage, rate, s=23, color=color)
        offsets = {'direct': (6, -17), 'draft': (0, 15), 'target_only': (3, 9), 'cure_l': (-5, -16)}
        if method in offsets:
            cost.annotate(NAMES[method], (usage, rate), xytext=offsets[method], textcoords='offset points',
                          fontsize=6, ha='right' if method == 'cure_l' else 'left', arrowprops={'arrowstyle': '-', 'lw': .5})
        if method in pairs:
            effect, low, high = (100*float(pairs[method][key]) for key in ('difference', 'ci_low', 'ci_high'))
            paired.errorbar(effect, index, xerr=[[effect-low], [high-effect]], fmt='o', markersize=3, capsize=2, color='#147d73')
    accuracy.set(yticks=range(len(LABELS)), yticklabels=LABELS, xlim=(0, 100), xlabel='All-attempt accuracy (%)', title='(a) All 120 questions')
    paired.set(yticks=range(len(LABELS)-1), yticklabels=LABELS[:-1], xlabel='CURE minus control (pp)', title='(b) Paired intervals')
    paired.axvline(0, color='.6', ls='--', lw=.8)
    cost.set(xlabel='Reported tokens / task (k)', ylabel='All-attempt accuracy (%)', ylim=(0, 100), title='(c) Delivery and logical usage')
    accuracy.invert_yaxis()
    paired.invert_yaxis()
    figure.tight_layout(w_pad=1)
    save(figure, 'workflow-comparison')

    terminal = {row['method']: row for row in read_csv(results/'terminal_scores.csv')}
    partition = next(row for row in read_csv(results/'primary_partition.csv') if row['method'] == 'cure_l' and row['family'] == 'all')
    figure, (status, waterfall) = plt.subplots(1, 2, figsize=(7.16, 3), gridspec_kw={'width_ratios': [1.15, 1]})
    left = [0] * len(ORDER)
    for field, name, color in (('matches', 'Match', '#32658b'), ('nonempty_mismatch', 'Nonempty mismatch', '#b65b55'),
                               ('returned_empty', 'Returned empty', '#d1a246'), ('unavailable', 'Unavailable', '#c9cdd0')):
        values = [int(terminal[method][field]) for method in ORDER]
        status.barh(range(len(values)), values, left=left, color=color, label=name)
        left = [start+value for start, value in zip(left, values)]
    status.set(yticks=range(len(LABELS)), yticklabels=LABELS, xlim=(0, 120), xticks=(0, 30, 60, 90, 120),
               xlabel='Questions (all attempts)', title='(a) Distinct terminal outcomes')
    status.invert_yaxis()
    draft = current = int(partition['draft'])
    waterfall.bar(0, draft, color='#32658b')
    waterfall.text(0, draft+1, str(draft), ha='center')
    labels = ('Draft', 'Repair', 'Wrong', 'Empty', 'Missing', 'Final')
    for index, field in enumerate(('repair', 'wrong_regression', 'empty_loss', 'delivery_loss'), 1):
        delta = int(partition[field]) * (1 if index == 1 else -1)
        following = current + delta
        waterfall.bar(index, abs(delta), bottom=min(current, following), color='#208479' if delta > 0 else '#b65b55')
        waterfall.plot([index-.6, index-.4], [current, current], color='.55', lw=.6)
        waterfall.text(index, max(current, following)+1, f'{delta:+d}', ha='center')
        current = following
    waterfall.bar(5, current, color='#208479')
    waterfall.text(5, current+1, str(current), ha='center')
    waterfall.set(xticks=range(6), xticklabels=labels, ylim=(0, 105), ylabel='Strict matches', title='(b) CURE: loss of matching drafts')
    handles, legend = status.get_legend_handles_labels()
    figure.legend(handles, legend, loc='lower center', ncol=4, frameon=False, fontsize=7)
    figure.tight_layout(rect=(0, .07, 1, 1), w_pad=1.1)
    save(figure, 'terminal-outcomes')

    curves = [row for row in read_csv(results/'fault_curves.csv') if row['cohort'] == 'extension' and float(row['p']) <= .4]
    figure, axes = plt.subplots(1, 2, figsize=(3.5, 2.18), sharey=True)
    for axis, dependence, title in zip(axes, ('independent', 'common'), ('Independent loss', 'Common outage')):
        for policy, color, style in zip(('original', 'agreement', 'fallback', 'both'),
                                        ('#353b48', '#d88b20', '#2476a4', '#24845b'), ('-', '--', '-.', ':')):
            rows = [row for row in curves if row['dependence'] == dependence and row['policy'] == policy]
            axis.plot([float(row['p']) for row in rows], [100*float(row['expected_correct'])/int(row['n']) for row in rows],
                      color=color, ls=style, lw=1.45, label=policy.capitalize())
        axis.set(title=title, xlabel='Assumed stage-loss probability', xticks=(0, .2, .4), ylim=(0, 85))
        axis.xaxis.label.set_size(6.5)
        axis.grid(alpha=.18)
    axes[0].set_ylabel('Expected strict matches (%)')
    axes[1].text(.02, .03, 'Original = fallback\nAgreement = both', transform=axes[1].transAxes, fontsize=6.3)
    handles, legend = axes[0].get_legend_handles_labels()
    figure.legend(handles, legend, loc='lower center', ncol=4, frameon=False, fontsize=6.6, columnspacing=.8, handlelength=1.6)
    figure.tight_layout(rect=(0, .11, 1, 1), pad=.35)
    save(figure, 'fault-sensitivity')
