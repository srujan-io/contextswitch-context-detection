"""Draw every recognized hand; one designated hand still owns the pointer."""
import math
def draw_hands(frame,hands,labels,primary,availability,connections,cv):
    height,width=frame.shape[:2]
    for i,landmarks in enumerate(hands):
        if len(landmarks)!=21 or not all(math.isfinite(p.x) and math.isfinite(p.y) for p in landmarks):continue
        color=(100,225,140) if i==primary else (235,190,90)
        if not availability['hands'][i]['fully_visible']:color=(60,150,240)
        for start,end in connections:
            a,b=landmarks[start],landmarks[end]
            cv.line(frame,(int(a.x*width),int(a.y*height)),(int(b.x*width),int(b.y*height)),color,2)
        for point in landmarks:cv.circle(frame,(int(point.x*width),int(point.y*height)),3,color,-1)
        wrist=landmarks[0]
        cv.putText(frame,f"{labels[i]}{' / pointer' if i==primary else ''}",(max(5,min(width-150,int(wrist.x*width))),max(70,min(height-10,int(wrist.y*height)))),cv.FONT_HERSHEY_SIMPLEX,.45,color,1,cv.LINE_AA)
    cv.putText(frame,f"Hands: {len(hands)}/2 | fully in frame: {availability['fully_visible_count']}/2",(12,50),cv.FONT_HERSHEY_SIMPLEX,.5,(220,230,210),1,cv.LINE_AA)
