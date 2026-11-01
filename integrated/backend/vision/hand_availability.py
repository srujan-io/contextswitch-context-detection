"""Visible-landmark and grasp-pose heuristics; not an object/occupation detector."""
def assess_hands(hands):
    evidence=[]
    for hand in hands:
        full=len(hand)==21 and all(.025<p.x<.975 and .025<p.y<.975 for p in hand)
        extended=sum(hand[tip].y<hand[pip].y for tip,pip in ((8,6),(12,10),(16,14),(20,18))) if len(hand)==21 else 0
        ready=full and extended>=1
        evidence.append({'fully_visible':full,'control_ready':ready,'extended_fingers':extended,
                         'possibly_occupied':full and extended==0})
    count=len(evidence);full=sum(h['fully_visible'] for h in evidence)
    return {'hand_count':count,'fully_visible_count':full,'both_hands_visible':count==2 and full==2,
            'two_hands_possibly_occupied':count==2 and all(h['possibly_occupied'] for h in evidence),
            'incomplete_frame':count<2 or full<count,'hands':evidence,'occupation_kind':'pose heuristic; object use is not verified'}
