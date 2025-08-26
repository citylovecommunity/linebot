from graphviz import Digraph

# 大原則：一個dispatcher，一個泡泡；一個response，一個網頁介面

dot = Digraph()


wait_for_response_states = [
    'invitation',
    'liked',
    'rest_r1',
    'rest_r2',
    'rest_r3',
    'rest_r4',
]


states = [
    'no_action_goodbye_sending',
    'goodbye',
    'deal_sending',
    'deal_1d_notification_sending',
    'deal_3hr_notification_sending',
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

    dot.edge(s+'_response', s+'_response',
             label=f'Cron triggers 24/48 {s} notification dispatcher',
             color='blue')

    dot.edge(s+'_sending', s+'_waiting',
             label=f'Cron triggers {s} dispatcher',
             color='blue')
    dot.edge(s+'_waiting', s+'_response')

    dot.edge(s+'_response', 'no_action_goodbye_sending',
             label='No action ≥72h', style='dashed', color='red')


# Main flow
dot.edge('invitation_response', 'liked_sending')
dot.edge('liked_response', 'goodbye_sending', label='decline')
dot.edge('liked_response', 'rest_r1_sending', label='accept')

dot.edge('goodbye_sending', 'goodbye',
         label='Cron triggers goodbye_sending dispatcher',
         color='blue')
dot.edge('rest_r1_response', 'rest_r2_sending')

dot.edge('rest_r2_response', 'rest_r3_sending', label='decline')
dot.edge('rest_r2_response', 'deal_sending', label='accept')

dot.edge('rest_r3_response', 'rest_r4_sending', label='accept')
dot.edge('rest_r3_response', 'next_month_sending', label='reject')


dot.edge('next_month_sending', 'next_month_waiting',
         label='Cron triggers next_month_sending dispatcher',
         color='blue')

dot.edge('next_month_waiting', 'rest_r1_next_month_sending',
         label='Cron triggers transformers rest_r1_next_month_sending')

dot.edge('rest_r1_next_month_sending', 'rest_r1_waiting',
         label='Cron triggers rest_r1_next_month_sending dispatcher',
         color='blue')


dot.edge('rest_r4_response', 'next_month_sending', label='reject')
dot.edge('rest_r4_response', 'deal_sending', label='accept')
dot.edge('no_action_goodbye_sending', 'goodbye',
         label=f'Cron triggers no_action_goodbye_sending dispatcher',
         color='blue')


sending_edges = [('deal_sending', 'deal_1d_notification_sending'),
                 ('deal_1d_notification_sending', 'deal_3hr_notification_sending'),
                 ('deal_3hr_notification_sending', 'dating_notification_sending'),
                 ('dating_notification_sending', 'dating_feedback_sending'),
                 ('dating_feedback_sending', 'dating_done'),
                 ('sudden_change_time_notification_sending', 'change_time_sending')
                 ]
for from_node, to_node in sending_edges:
    dot.edge(from_node, to_node, label=f'Cron triggers {from_node} dispatcher',
             color='blue')


dot.edge('deal_1d_notification_sending', 'sudden_change_time_notification_sending',
         label='Someone triggers change time', color='red')


dot.edge('change_time_sending', 'rest_r1_waiting',
         label='Cron triggers change_time_sending dispatcher',
         color='blue')


dot.edge('deal_3hr_notification_sending', 'next_month_sending',
         label='Someone triggers change time next month.',
         color='red')

dot.edge('dating_notification_sending', 'next_month_sending',
         label='Someone triggers change time next month.',
         color='red')

dot.attr(ranksep='1.5', nodesep='1.0')
dot.attr('edge', arrowsize='3', penwidth='3')
dot.render('flowchart', format='png', cleanup=True)
