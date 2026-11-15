// SPDX-License-Identifier: GPL-3.0-or-later
#include "optics/thin_lens.h"

#include <cmath>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

using namespace tilt_shift;
namespace {
int checks = 0;
constexpr double pi = 3.14159265358979323846;
void check(bool value, const std::string &message)
{
  ++checks;
  if (!value) throw std::runtime_error(message);
}
void close(double a, double b, double tolerance, const std::string &message)
{
  check(std::isfinite(a) && std::isfinite(b) && std::abs(a - b) <= tolerance, message);
}
void close(Vec3 a, Vec3 b, double tolerance, const std::string &message)
{
  check(length(a - b) <= tolerance, message);
}
void rejects(const std::function<void()> &action, const std::string &message)
{
  bool rejected = false;
  try { action(); }
  catch (const std::invalid_argument &) { rejected = true; }
  check(rejected, message);
}
Vec3 at_z(Ray ray, double z)
{
  return ray.origin + ray.direction * ((z - ray.origin.z) / ray.direction.z);
}
// Independent forward propagation: Gaussian thin-lens transverse slope kick,
// using the object-to-aperture incident ray, then intersection with sensor Z.
Vec3 forward_image(const ThinLens &camera, Vec3 object, Vec3 aperture)
{
  const Vec3 n = camera.normal();
  const double u = dot(object, n);
  const Vec3 transverse_object = object - n * u;
  const Vec3 outgoing_slope = (transverse_object - aperture) / u +
                              aperture / camera.parameters().focal_length;
  const Vec3 outgoing = n * -1.0 - outgoing_slope;
  return aperture + outgoing *
      ((-camera.sensor_distance() - aperture.z) / outgoing.z);
}
void gaussian_and_breathing()
{
  Parameters p;
  for (double focus : {0.15, 0.5, 5.0, 1000.0}) {
    p.focus_distance = focus;
    ThinLens camera(p);
    const double b = camera.sensor_distance();
    close(1.0 / p.focal_length, 1.0 / focus + 1.0 / b, 1e-13,
          "Gaussian lens equation");
    check(b > p.focal_length, "Physical finite focus extends sensor");
    const Ray edge = camera.ray_at(1, 0, 0, 0);
    close(-edge.direction.x / edge.direction.z, p.sensor_width / (2 * b), 1e-15,
          "Physical framing uses b, not nominal f");
    check(-edge.direction.x / edge.direction.z < p.sensor_width / (2*p.focal_length),
          "Finite-focus physical framing differs from fixed-f graphics camera");
    close(at_z(camera.ray_at(0, 0, 1, 0), focus), {0, 0, focus}, 1e-11,
          "Axis focus shared by aperture edge");
  }
  p.focus_distance = std::numeric_limits<double>::infinity();
  ThinLens infinity(p);
  close(infinity.sensor_distance(), p.focal_length, 0, "Infinity sensor at f");
  close(length(infinity.focus_plane().normal), 0, 0, "Untilting at infinity has no finite sharp plane");
  close(infinity.focus_plane().offset, p.focal_length, 0, "Plane at infinity homogeneous offset");
}
void rotations_and_signs()
{
  Parameters p;
  p.tilt = 0.13; p.swing = -0.08; p.axis_rotation = 0.37;
  ThinLens c(p);
  const Vec3 expected{
      std::cos(p.axis_rotation)*std::sin(p.swing)*std::cos(p.tilt) +
          std::sin(p.axis_rotation)*std::sin(p.tilt),
      std::sin(p.axis_rotation)*std::sin(p.swing)*std::cos(p.tilt) -
          std::cos(p.axis_rotation)*std::sin(p.tilt),
      std::cos(p.swing)*std::cos(p.tilt)};
  close(c.normal(), expected, 1e-15, "Declared Euler rotation order");
  close(cross(c.aperture_x(), c.aperture_y()), c.normal(), 1e-15,
        "Aperture basis right handed");
  close(dot(c.aperture_x(), c.aperture_y()), 0, 1e-15, "Aperture axes perpendicular");
  close(length(c.normal()), 1, 1e-15, "Lens normal unit length");
  // Swapping Rx and Ry changes the normal when both movements are nonzero.
  const Vec3 swapped{std::sin(p.swing),
      -std::sin(p.tilt)*std::cos(p.swing), std::cos(p.tilt)*std::cos(p.swing)};
  const Vec3 swapped_rotated{
      std::cos(p.axis_rotation)*swapped.x - std::sin(p.axis_rotation)*swapped.y,
      std::sin(p.axis_rotation)*swapped.x + std::cos(p.axis_rotation)*swapped.y,
      swapped.z};
  check(length(c.normal() - swapped_rotated) > 1e-4, "Rotation noncommutativity");
  for (double sign : {-1.0, 1.0}) {
    p.axis_rotation = 0; p.swing = 0; p.tilt = sign*0.1;
    ThinLens tilted(p);
    const Plane plane = tilted.focus_plane();
    const double depth_positive_y = (plane.offset - plane.normal.y*0.01) / plane.normal.z;
    check(sign*(depth_positive_y-p.focus_distance) > 0, "Signed tilt depth gradient");
    p.tilt = 0; p.swing = sign*0.1;
    ThinLens swung(p);
    const Plane swing_plane = swung.focus_plane();
    const double depth_right = (swing_plane.offset-swing_plane.normal.x*0.01) /
                               swing_plane.normal.z;
    check(sign*(depth_right-p.focus_distance) < 0, "Signed swing depth gradient");
  }
}
void scheimpflug_hinge_and_rays()
{
  int rays = 0;
  for (double tilt : {-0.18, 0.0, 0.11}) {
    for (double swing : {-0.09, 0.0, 0.14}) {
      for (double axis : {0.0, 0.43, 1.57}) {
        Parameters p;
        p.tilt=tilt; p.swing=swing; p.axis_rotation=axis;
        p.shift_x=0.004; p.shift_y=-0.002;
        ThinLens c(p);
        const Vec3 n=c.normal();
        const Plane plane=c.focus_plane();
        close(dot(plane.normal,{0,0,p.focus_distance}),plane.offset,1e-15,
              "Focus convention fixed camera axis");
        const double transverse2=n.x*n.x+n.y*n.y;
        if (transverse2 > 1e-20) {
          const Vec3 line_direction=normalized(cross({0,0,1},n));
          const Vec3 scheimpflug{n.x*n.z*c.sensor_distance()/transverse2,
                                n.y*n.z*c.sensor_distance()/transverse2,
                                -c.sensor_distance()};
          const Vec3 hinge{p.focal_length*n.x/transverse2,
                           p.focal_length*n.y/transverse2,0};
          close(length(hinge),p.focal_length/std::sqrt(transverse2),1e-14,
                "Hinge distance f/sin(total lens angle)");
          for (double t : {-2.0,0.0,1.7}) {
            const Vec3 s=scheimpflug+line_direction*t;
            close(s.z,-c.sensor_distance(),1e-15,"Scheimpflug on sensor plane");
            close(dot(n,s),0,1e-15,"Scheimpflug on lens plane");
            close(dot(plane.normal,s),plane.offset,1e-14,"Scheimpflug on sharp plane");
            const Vec3 h=hinge+line_direction*t;
            close(h.z,0,1e-15,"Hinge on parallel-to-sensor lens plane");
            close(dot(n,h),p.focal_length,1e-15,"Hinge on front focal plane");
            close(dot(plane.normal,h),plane.offset,1e-15,"Hinge on sharp plane");
          }
          Parameters refocused=p; refocused.focus_distance=1.3;
          const Plane other=ThinLens(refocused).focus_plane();
          close(dot(other.normal,hinge),other.offset,1e-15,
                "Refocusing pivots sharp plane around same hinge");
        }
        for (double sx : {-1.0,-0.4,0.0,0.8,1.0}) {
          for (double sy : {-1.0,0.0,1.0}) {
            const Vec3 sensor=c.sensor_point(sx,sy);
            const Conjugate q=c.conjugate(sx,sy);
            for (double u : {0.0,0.2,0.7,1.0}) {
              const Ray r=c.sample_ray(sx,sy,u,0.317);
              ++rays;
              close(length(r.direction),1,1e-15,"Ray unit direction");
              close(dot(n,r.origin),0,1e-17,"Aperture on tilted lens plane");
              close(length(r.origin),p.aperture_radius*std::sqrt(u),1e-17,
                    "Uniform disk area quantile");
              check(dot(n,r.direction)>0,"Scene-going ray");
              const Vec3 vin=(r.origin-sensor)/(-dot(n,sensor));
              const Vec3 vout=r.direction/dot(n,r.direction);
              close(vout-vin,r.origin*(-1/p.focal_length),1e-14,
                    "Independent paraxial refraction slope kick");
              if (std::abs(q.denominator)>1e-9) {
                const Vec3 point=q.numerator/q.denominator;
                close(dot(plane.normal,point),plane.offset,1e-12,
                      "Conjugate on derived sharp plane");
                close(length(cross(point-r.origin,r.direction)),0,1e-10,
                      "Aperture rays share conjugate, including virtual case");
                if (q.denominator<0) {
                  check(dot(point-r.origin,r.direction)>0,"Real conjugate in forward ray");
                  close(forward_image(c,point,r.origin),sensor,1e-12,
                        "Independent forward sensor reconstruction");
                }
              }
            }
          }
        }
      }
    }
  }
  check(rays==1620,"Deterministic pose/sensor/aperture matrix complete");
}
void infinity_virtual_and_zero_aperture()
{
  Parameters p;
  p.focus_distance=std::numeric_limits<double>::infinity();
  for (double tilt : {0.0,0.14}) {
    p.tilt=tilt;
    ThinLens c(p);
    for (double sx : {-1.0,0.0,1.0}) {
      // For pure tilt, y=0 lies on the collimated locus h=0.
      close(c.conjugate(sx,0).denominator,0,3e-16,"Infinity homogeneous denominator");
      close(c.ray_at(sx,0,0,0).direction,c.ray_at(sx,0,1,0).direction,1e-15,
            "Infinity rays parallel for all apertures");
    }
    if (tilt!=0) {
      check(c.conjugate(0,-1).denominator>0,"Virtual-focus sensor region supported");
      check(c.conjugate(0,1).denominator<0,"Real-focus sensor region supported");
    }
    // Smoothly cross the real/infinite/virtual boundary; no enormous focus point.
    const Vec3 dm=c.ray_at(0,-1e-7,0.8,0).direction;
    const Vec3 dp=c.ray_at(0,1e-7,0.8,0).direction;
    check(length(dm-dp)<1e-6,"Continuous ray across infinity");
  }
  p.aperture_radius=0; p.focus_distance=2; p.swing=0.08;
  ThinLens c(p);
  close(c.ray_at(0.7,-0.4,1,0).origin,{0,0,0},0,"Zero aperture origin");
  close(c.ray_at(0.7,-0.4,1,0).direction,
        normalized(c.sensor_point(0.7,-0.4)*-1),1e-15,"Zero aperture pinhole limit");
}
void circle_of_confusion()
{
  Parameters p;
  for (double radius : {0.0,0.002,0.00625}) {
    p.aperture_radius=radius;
    ThinLens c(p);
    for (double object_depth : {0.2,1.0,5.0,12.0,1e8}) {
      const Vec3 a{radius,0,0}, b{-radius,0,0};
      const Vec3 i1=forward_image(c,{0,0,object_depth},a);
      const Vec3 i2=forward_image(c,{0,0,object_depth},b);
      const double expected=2*radius*std::abs(1-c.sensor_distance()*
          (1/p.focal_length-1/object_depth));
      close(length(i1-i2),expected,2e-16,"Analytic untilted CoC diameter");
      close((i1+i2)*0.5,{0,0,-c.sensor_distance()},1e-16,"CoC centred on chief ray");
    }
  }
}
void shift_and_coverage()
{
  Parameters p;
  p.aperture_radius=0; p.image_circle_radius=0.012;
  ThinLens base(p);
  p.shift_x=0.005; p.shift_y=-0.003;
  ThinLens shifted(p);
  close(shifted.sensor_point(0,0)-base.sensor_point(0,0),{0.005,-0.003,0},1e-16,
        "Shift translates physical sensor");
  const Vec3 direction=shifted.ray_at(0,0,0,0).direction;
  close(direction.x/direction.z,-p.shift_x/shifted.sensor_distance(),1e-15,
        "Shift changes chief ray framing");
  close(direction.y/direction.z,-p.shift_y/shifted.sensor_distance(),1e-15,
        "Vertical shift changes chief ray framing");
  close(shifted.focus_plane().normal,base.focus_plane().normal,0,
        "Sensor shift preserves sharp plane");
  close(shifted.normal(),base.normal(),0,"Shift does not tilt lens or convergence");
  check(base.covered(0,0),"Circle centre covered");
  check(!base.covered(1,1),"Outside angular coverage clipped");
  const double sensor_radius=p.image_circle_radius*base.sensor_distance()/p.focal_length;
  const double x=2*sensor_radius/p.sensor_width;
  check(base.covered(x*(1-1e-10),0),"Just inside coverage boundary");
  check(!base.covered(x*(1+1e-10),0),"Just outside coverage boundary");
  close(base.ray_at(1,1,0,0).weight,0,0,"Clipping is binary");
  close(base.ray_at(0,0,0,0).weight,1,0,"No arbitrary radial falloff");
  p.image_circle_radius=std::numeric_limits<double>::infinity();
  check(ThinLens(p).covered(1,1),"Infinite radius disables clipping");
  p.tilt=0.15; p.swing=-0.1; p.aperture_radius=0.005;
  p.image_circle_radius=0.016;
  ThinLens tilted(p);
  for(double sx : {-1.0,0.0,1.0}) for(double sy : {-1.0,0.0,1.0}) {
    const Vec3 sensor=tilted.sensor_point(sx,sy), n=tilted.normal();
    // Independent equivalent angle test tan(theta) <= radius/f.
    const Vec3 chief=normalized(sensor*-1);
    const double cos_angle=dot(chief,n);
    const double tan_angle=length(cross(chief,n))/cos_angle;
    check(tilted.covered(sx,sy)==(tan_angle<=p.image_circle_radius/p.focal_length),
          "Tilted coverage equals prescribed circular angular cone");
    close(tilted.ray_at(sx,sy,1,0).weight,tilted.ray_at(sx,sy,0,1).weight,0,
          "Coverage gate independent of aperture sample");
  }
}
void invalid_inputs()
{
  const double nan=std::numeric_limits<double>::quiet_NaN();
  const double inf=std::numeric_limits<double>::infinity();
  auto bad=[](const std::function<void(Parameters&)> &edit) {
    Parameters p; edit(p); rejects([&]{ThinLens c(p);},"Invalid configuration rejected");
  };
  bad([](Parameters&p){p.focal_length=0;});
  bad([&](Parameters&p){p.focal_length=nan;});
  bad([](Parameters&p){p.focus_distance=0;});
  bad([](Parameters&p){p.focus_distance=-1;});
  bad([&](Parameters&p){p.focus_distance=nan;});
  bad([](Parameters&p){p.focus_distance=p.focal_length;});
  bad([](Parameters&p){p.focus_distance=p.focal_length*0.5;});
  bad([](Parameters&p){p.focus_distance=p.focal_length/(1-5e-15);});
  bad([](Parameters&p){p.sensor_width=0;});
  bad([&](Parameters&p){p.sensor_height=inf;});
  bad([&](Parameters&p){p.shift_x=nan;});
  bad([&](Parameters&p){p.tilt=inf;});
  bad([](Parameters&p){p.tilt=pi/2;});
  bad([](Parameters&p){p.tilt=pi/2-1e-15;p.focus_distance=std::numeric_limits<double>::infinity();});
  bad([](Parameters&p){p.swing=pi;});
  bad([](Parameters&p){p.tilt=0.3;p.shift_y=-1;});
  bad([](Parameters&p){p.tilt=0.3;p.aperture_radius=1;});
  bad([](Parameters&p){p.aperture_radius=-0.01;});
  bad([&](Parameters&p){p.aperture_radius=inf;});
  bad([](Parameters&p){p.image_circle_radius=-1;});
  bad([&](Parameters&p){p.image_circle_radius=nan;});
  ThinLens c(Parameters{});
  rejects([&]{c.ray_at(1.01,0,0,0);},"Out of sensor domain rejected");
  rejects([&]{c.ray_at(0,nan,0,0);},"NaN sensor rejected");
  rejects([&]{c.ray_at(0,0,0.8,0.8);},"Out of disk domain rejected");
  rejects([&]{c.sample_ray(0,0,-0.1,0);},"Negative aperture variate rejected");
  rejects([&]{c.sample_ray(0,0,0,1.1);},"Out of aperture variate rejected");
  rejects([&]{c.sample_ray(0,0,nan,0);},"NaN aperture variate rejected");
  rejects([&]{normalized({0,0,0});},"Zero vector rejected");
  // Scale covariance: all lengths scale, directions and coverage do not.
  Parameters p; p.tilt=.12;p.swing=-.09;p.shift_x=.003;p.image_circle_radius=.02;
  ThinLens original(p);
  for(double scale : {1e-6,1e6}) {
    Parameters q=p;
    q.focal_length*=scale;q.focus_distance*=scale;q.sensor_width*=scale;
    q.sensor_height*=scale;q.shift_x*=scale;q.shift_y*=scale;
    q.aperture_radius*=scale;q.image_circle_radius*=scale;
    ThinLens scaled(q);
    const Ray a=original.sample_ray(.7,-.6,.8,.4), b=scaled.sample_ray(.7,-.6,.8,.4);
    close(a.direction,b.direction,2e-15,"Units do not change ray direction");
    close(a.origin,b.origin/scale,1e-17,"Units scale aperture origin");
    close(a.weight,b.weight,0,"Units preserve angular coverage");
  }
}
} // namespace
int main()
{
  try {
    gaussian_and_breathing();
    rotations_and_signs();
    scheimpflug_hinge_and_rays();
    infinity_virtual_and_zero_aperture();
    circle_of_confusion();
    shift_and_coverage();
    invalid_inputs();
    std::cout << "PASS: " << checks << " optical checks; 1620 deterministic rays\n";
  }
  catch(const std::exception &e) {
    std::cerr << "FAIL after " << checks << " checks: " << e.what() << '\n';
    return 1;
  }
}
