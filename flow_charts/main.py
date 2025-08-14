from graphviz import Digraph

dot = Digraph()


wait_for_response_states = [
    'invitation',
    'liked',
    'rest_r1',
    'rest_r2',
    'rest_r3',
    'rest_r4',
    'change_time'
]


states = [
    'no_action_goodbye_sending',
    'goodbye',
    'deal_sending',
    'deal_1d_notification_sending',
    'deal_3hr_notification_sending',
    'dating_finished',
    'sudden_change_time_notification_sending',
    'next_month_sending',
    'next_month_waiting'
]


for s in states:
    dot.node(s, shape='ellipse')


for s in wait_for_response_states:
    dot.node(s+'_sending', shape='ellipse')
    dot.node(s+'_waiting', shape='ellipse')
    dot.node(s+'_response', shape='diamond')

    dot.edge(s+'_sending', s+'_waiting', label=f'Cron triggers {s} dispatcher')
    dot.edge(s+'_waiting', s+'_response')

    if s not in ('invitation', 'liked'):
        dot.edge(s+'_response', 'no_action_goodbye_sending',
                 label='No action ≥48h', style='dashed', color='red')
    else:
        dot.edge(s+'_response', 'goodbye',
                 label='No action ≥48h', style='dashed', color='red')


# Main flow
dot.edge('invitation_response', 'liked_sending')
dot.edge('liked_response', 'goodbye_sending', label='decline')
dot.edge('liked_response', 'rest_r1_sending', label='accept')

dot.edge('goodbye_sending', 'goodbye',
         label='Cron triggers goodbye_sending dispatcher')
dot.edge('rest_r1_response', 'rest_r2_sending')

dot.edge('rest_r2_response', 'rest_r3_sending', label='decline')
dot.edge('rest_r2_response', 'deal_sending', label='accept')

dot.edge('rest_r3_response', 'rest_r4_sending', label='accept')
dot.edge('rest_r3_response', 'next_month_sending', label='reject')


dot.edge('next_month_sending', 'next_month_waiting',
         label='Cron triggers next_month_sending dispatcher')
dot.edge('next_month_waiting', 'rest_r1_sending',
         label='Cron triggers transformers next_month_waiting')


dot.edge('rest_r4_response', 'goodbye_sending', label='reject')
dot.edge('rest_r4_response', 'deal_sending', label='accept')
dot.edge('no_action_goodbye_sending', 'goodbye',
         label=f'Cron triggers no_action_goodbye_sending dispatcher')


sending_edges = [('deal_sending', 'deal_1d_notification_sending'),
                 ('deal_1d_notification_sending', 'deal_3hr_notification_sending'),
                 ('deal_3hr_notification_sending', 'dating_finished'),
                 ('sudden_change_time_notification_sending', 'change_time_sending')
                 ]
for from_node, to_node in sending_edges:
    dot.edge(from_node, to_node, label=f'Cron trigger {from_node} dispatcher')


dot.edge('deal_1d_notification_sending', 'sudden_change_time_notification_sending',
         label='Some one triggers change time', color='red')
dot.edge('deal_3hr_notification_sending',
         'sudden_change_time_notification_sending', label='Some one triggers change time', color='red')


dot.edge('change_time_response', 'rest_r1_waiting')


# sdot.attr(ranksep='1.5', nodesep='1.0')
dot.render('waiting_timeout_rule', format='png', cleanup=True)
