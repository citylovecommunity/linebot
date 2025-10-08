from graphviz import Digraph


dot = Digraph(engine='circo')


wait_for_response_states = [
    'invitation',
    'liked',
    'rest_r1',
    'rest_r2',
    'rest_r3',
    'rest_r4',
]


for s in wait_for_response_states:
    dot.node(s+'_sending', shape='ellipse')
    dot.node(s+'_waiting', shape='ellipse')
    dot.node(s+'_response', shape='diamond')

    dot.edge(s+'_sending', s+'_waiting',
             color='blue')
    dot.edge(s+'_waiting', s+'_response')


# Main flow
dot.edge('invitation_response', 'liked_sending')

dot.edge('liked_response', 'rest_r1_sending')


dot.edge('rest_r1_response', 'rest_r2_sending')

dot.edge('rest_r2_response', 'rest_r3_sending', label='decline')
dot.edge('rest_r2_response', 'deal_sending', label='accept')

dot.edge('rest_r3_response', 'rest_r4_sending', label='accept')
dot.edge('rest_r3_response', 'next_time_sending', label='reject')


dot.edge('next_time_sending', 'rest_r1_next_time_sending',
         color='blue')


dot.edge('rest_r1_next_time_sending', 'rest_r1_waiting',
         color='blue')


dot.edge('rest_r4_response', 'next_time_sending', label='reject')
dot.edge('rest_r4_response', 'deal_sending', label='accept')


sending_edges = [('deal_sending', 'deal_1d_notification_sending'),
                 ('deal_1d_notification_sending', 'deal_3hr_notification_sending'),
                 ('deal_3hr_notification_sending', 'dating_feedback_sending'),
                 ('dating_feedback_sending', 'dating_done'),
                 ('change_time_notification_sending', 'rest_r1_next_time_sending')
                 ]
for from_node, to_node in sending_edges:
    dot.edge(from_node, to_node, color='blue')


dot.edge('deal_1d_notification_sending', 'change_time_notification_sending',
         label='Someone triggers change time', color='red')


dot.edge('deal_3hr_notification_sending', 'change_time_notification_sending',
         label='Someone triggers change time.',
         color='red')


dot.edge('dating_feedback_sending', 'change_time_notification_sending',
         label='Someone triggers change time next time.',
         color='red')


dot.render('flowchart', format='png', cleanup=True)
