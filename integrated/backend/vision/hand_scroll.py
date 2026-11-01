"""Two raised fingers + vertical motion scroll; no click or zoom in this pose."""
class HandScroll:
    def __init__(self):self.last_y=None;self.since=None
    def process(self,hand,now):
        if not hand or not hand.get('detected') or not hand.get('scroll_pose') or hand.get('pinching'):
            self.last_y=self.since=None;return []
        y=hand['index_y']
        if self.since is None:self.since=now;self.last_y=y;return [('PINCH_CANCEL',{})]
        if now-self.since<.2:self.last_y=y;return []
        distance=y-self.last_y;self.last_y=y
        if abs(distance)<.003:return []
        return [('SCROLL',{'delta_y':round(max(-100,min(100,distance*1200)),2)})]
