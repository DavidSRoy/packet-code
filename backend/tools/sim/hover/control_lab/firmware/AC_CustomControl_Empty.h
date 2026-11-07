#pragma once
#include "AC_CustomControl_config.h"
#if CONFIG_HAL_BOARD != HAL_BOARD_SITL
#error "Packet experimental LQG is simulation-only; do not build for flight hardware"
#endif
#if AP_CUSTOMCONTROL_EMPTY_ENABLED
#include "AC_CustomControl_Backend.h"
#include "PacketLQGCore.h"
class AC_CustomControl_Empty : public AC_CustomControl_Backend {
public:
    AC_CustomControl_Empty(AC_CustomControl&, AP_AHRS_View*&, AC_AttitudeControl*&, AP_MotorsMulticopter*&, float);
    Vector3f update(void) override;
    void reset(void) override;
    static const struct AP_Param::GroupInfo var_info[];
protected:
    AP_Float param1, param2, param3;
    PacketLQG::Core axis[3];
    bool ready=false;
    float _dt;
    uint8_t log_count=0;
};
#endif
