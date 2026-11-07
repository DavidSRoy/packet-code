#include "AC_CustomControl_config.h"
#if AP_CUSTOMCONTROL_EMPTY_ENABLED
#include "AC_CustomControl_Empty.h"
#include <AP_Logger/AP_Logger.h>
const AP_Param::GroupInfo AC_CustomControl_Empty::var_info[] = {
    AP_GROUPINFO("PARAM1",1,AC_CustomControl_Empty,param1,1.0f),
    AP_GROUPINFO("PARAM2",2,AC_CustomControl_Empty,param2,0.15f),
    AP_GROUPINFO("PARAM3",3,AC_CustomControl_Empty,param3,0.0f),
    AP_GROUPEND
};
AC_CustomControl_Empty::AC_CustomControl_Empty(AC_CustomControl& f,AP_AHRS_View*& a,AC_AttitudeControl*& c,AP_MotorsMulticopter*& m,float dt):
    AC_CustomControl_Backend(f,a,c,m,dt), _dt(dt) {
    AP_Param::setup_object_defaults(this,var_info);
}
void AC_CustomControl_Empty::reset(void) { ready=false; }
Vector3f AC_CustomControl_Empty::update(void) {
    const Vector3f main{_motors->get_roll(),_motors->get_pitch(),_motors->get_yaw()};
    // The frontend refuses activation unless the configured loop is 400 Hz.
    const auto spool=_motors->get_spool_state();
    if (spool==AP_Motors::SpoolState::SHUT_DOWN || spool==AP_Motors::SpoolState::GROUND_IDLE) {
        ready=false; return main;
    }
    Quaternion q;
    _ahrs->get_quat_body_to_ned(q);
    Vector3f actual, target;
    q.to_euler(actual.x,actual.y,actual.z);
    _att_control->get_attitude_target_quat().to_euler(target.x,target.y,target.z);
    const Vector3f gyro=_ahrs->get_gyro_latest();
    Vector3f target_rate{};
    if (param3.get()>0.5f) {
        _att_control->body_to_euler_derivative(_att_control->get_attitude_target_quat(),
                                              _att_control->get_attitude_target_ang_vel(),target_rate);
    }
    if (!ready) {
        for (unsigned i=0;i<3;i++) axis[i].reset(actual[i],gyro[i]);
        ready=true;
    }
    const unsigned bank=unsigned(constrain_float(param1.get(),0.0f,2.0f));
    const float limit=constrain_float(param2.get(),0.01f,0.35f);
    Vector3f output;
    for (unsigned i=0;i<3;i++) {
        // Keep both measured yaw and reference on the observer's local branch.
        actual[i]=axis[i].state[0]+wrap_PI(actual[i]-axis[i].state[0]);
        target[i]=actual[i]+wrap_PI(target[i]-actual[i]);
        output[i]=axis[i].update(actual[i],gyro[i],target[i],i==2?1:0,bank,limit,target_rate[i]);
    }
    if (++log_count==40) {
        log_count=0;
        AP::logger().Write("PKLQ","TimeUS,Bank,R,P,Y","QBfff",AP_HAL::micros64(),bank,
                           output.x,output.y,output.z);
    }
    return output;
}
#endif
