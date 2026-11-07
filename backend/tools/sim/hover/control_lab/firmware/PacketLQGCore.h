#pragma once
#include <algorithm>
#include <cmath>
#include "PacketLQGMatrices.h"
namespace PacketLQG {
struct Core {
    double state[N]{};
    void reset(double angle, double rate) {
        std::fill(state, state+N, 0.0);
        state[0]=angle; state[1]=rate; state[5]=rate;
        for (int i=QUEUE_LAST+1;i<N;i++) state[i]=rate;
    }
    double update(double angle, double rate, double target, unsigned model, unsigned bank, double limit, double target_rate=0.) {
        double posterior[N], next[N]{};
        const double ea=angle-state[0], er=rate-state[GYRO_INDEX];
        for (int i=0;i<N;i++) {
            posterior[i]=state[i]+gain[model][i][0]*ea+gain[model][i][1]*er;
        }
        double raw=feedback[model][bank][0]*target+feedback[model][bank][1]*target_rate;
        for (int i=0;i<N;i++) raw-=feedback[model][bank][i]*posterior[i];
        const double output=std::max(-limit,std::min(limit,raw));
        for (int i=0;i<N;i++) {
            for (int j=0;j<N;j++) next[i]+=A[model][i][j]*posterior[j];
        }
        next[QUEUE_LAST]+=output; // use the clipped command in actuator prediction
        std::copy(next,next+N,state);
        return output;
    }
};
}
