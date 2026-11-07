"""Separate explicit gust transients from unfiltered post-gust stillness.

A recovery is confirmed only by a complete 20 s window, not a momentary crossing.
A trace cannot choose its own gust interval; the interval comes from test input.
"""
import numpy as np


def evaluate(t, position, attitude_deg, gust_start, gust_end, settled_start):
    t=np.asarray(t,float);p=np.asarray(position,float);a=np.asarray(attitude_deg,float)
    if (t.ndim!=1 or len(t)<2 or p.shape!=(len(t),3) or a.shape!=p.shape
            or not np.isfinite(np.r_[t,p.ravel(),a.ravel(),gust_start,gust_end,settled_start]).all()
            or np.any(np.diff(t)<=0) or not settled_start<gust_start<gust_end<=t[-1]):
        raise ValueError('Need finite ordered 3-axis samples and an explicit gust interval')
    if np.max(np.diff(t))>.05:
        raise ValueError('Gaps too large to certify a complete stillness window')
    a=np.degrees(np.unwrap(np.radians(a),axis=0))
    pre=(t>=settled_start)&(t<gust_start)
    if not pre.any():raise ValueError('Missing pre-gust hold')
    anchor=np.mean(p[pre],axis=0)
    after=t>=gust_start
    result={
        'gust_start_s':float(gust_start),'gust_end_s':float(gust_end),
        'peak_displacement_from_pre_gust_mean_mm':float(1000*np.max(np.linalg.norm(p[after]-anchor,axis=1))),
        'gust_and_recovery_angle_ptp_deg':np.ptp(a[after],axis=0).tolist(),
        'pre_gust_position_ptp_mm':(1000*np.ptp(p[pre],axis=0)).tolist(),
        'pre_gust_angle_ptp_deg':np.ptp(a[pre],axis=0).tolist(),
        'recovery_confirmed':False,'recovery_start_after_gust_s':None,
        'recovery_window_s':20.,
    }
    # 0.25 s search resolution, with every raw sample included in each window.
    for start in np.arange(gust_end,t[-1]-20+1e-9,.25):
        keep=(t>=start)&(t<=start+20)
        if t[keep][-1]-t[keep][0]<19.95:continue
        position_ptp=1000*np.ptp(p[keep],axis=0)
        angle_ptp=np.ptp(a[keep],axis=0)
        mean_error=1000*np.abs(np.mean(p[keep],axis=0)-anchor)
        if max(position_ptp)<2 and max(angle_ptp)<.1 and max(mean_error)<2:
            result.update(recovery_confirmed=True,recovery_start_after_gust_s=float(start-gust_end),
                          recovered_position_ptp_mm=position_ptp.tolist(),recovered_angle_ptp_deg=angle_ptp.tolist())
            break
    return result
