// SPDX-License-Identifier: GPL-3.0-or-later
#include <cmath>

#include "native/tilt_shift_math.h"
#include "optics/thin_lens.h"
#include <algorithm>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace ts = tilt_shift_native;
using namespace tilt_shift;
namespace {
int checks = 0;
double max_direction_error = 0, max_origin_error = 0;
void check(bool ok, const char *what)
{
  ++checks;
  if (!ok)
    throw std::runtime_error(what);
}
Vec3 reflect(ts::Vec v)
{
  return {v.x, -v.y, v.z};
}
Vec3 clipped(Ray r, double nearclip)
{
  return r.origin + r.direction * ((nearclip - r.origin.z) / r.direction.z);
}
void compare_ray(const ThinLens &c, ts::State s, double sx, double sy, double ax, double ay)
{
  const Vec3 p = c.sensor_point(sx, sy);
  const auto ref = c.ray_at(sx, sy, ax, ay);
  // Native incoming aperture Y follows Cycles up, reference aperture Y is down.
  const auto r = ts::sample(s,
                            float(-p.x / c.parameters().focal_length),
                            float(p.y / c.parameters().focal_length),
                            float(ax * c.parameters().aperture_radius),
                            float(-ay * c.parameters().aperture_radius));
  const double de = length(ref.direction - reflect(r.direction));
  const double oe = length(ref.origin - reflect(r.origin));
  max_direction_error = std::max(max_direction_error, de);
  max_origin_error = std::max(max_origin_error, oe);
  check(de < 4e-6, "float ray disagrees with independent double refraction reference");
  check(oe < 3e-8, "float tilted aperture origin disagrees with reference");
  check(r.weight == ref.weight, "float angular coverage disagrees with reference");
  const auto near = ts::clip_near(r, .1f);
  check(length(reflect(near.origin) - clipped(ref, .1)) < 8e-7,
        "camera-Z clipping disagrees with independently propagated reference "
        "ray");
  check(std::abs(near.origin.z - .1) < 2e-8, "clipped origin misses camera-Z near plane");
  const double far = .7;
  const auto endpoint = ts::add(near.origin,
                                ts::mul(near.direction, float((far - .1) / near.direction.z)));
  check(std::abs(endpoint.z - far) < 2e-7, "clip length misses camera-Z far plane");
}
void ray_matrix()
{
  for (double tilt : {-.18, 0., .11})
    for (double swing : {-.09, 0., .14})
      for (double axis : {0., .43, 1.57})
        for (double focus : {.15, .5, 5., 1000.}) {
          Parameters p;
          p.tilt = tilt;
          p.swing = swing;
          p.axis_rotation = axis;
          p.focus_distance = focus;
          p.shift_x = .004;
          p.shift_y = -.002;
          p.image_circle_radius = .022;
          ThinLens c(p);
          const auto s = ts::prepare(float(p.focal_length),
                                     float(focus),
                                     float(tilt),
                                     float(swing),
                                     float(axis),
                                     float(p.image_circle_radius));
          check(length(c.normal() - reflect(s.normal)) < 3e-7, "rotation/reflection signs");
          check(std::abs(c.sensor_distance() - s.sensor_distance) < 3e-8,
                "physical sensor distance");
          for (double sx : {-1., -.4, 0., .8, 1.})
            for (double sy : {-1., 0., 1.})
              for (double a : {0., .2, .7, 1.})
                compare_ray(c,
                            s,
                            sx,
                            sy,
                            std::sqrt(a) * std::cos(.317 * 2 * 3.141592653589793),
                            std::sqrt(a) * std::sin(.317 * 2 * 3.141592653589793));
        }
}
void physical_shift_and_focus_object()
{
  const float f = .05f, sensor_size = .036f, shift_x = .12f, shift_y = -.08f;
  const ts::Vec center{sensor_size * shift_x, sensor_size * shift_y, 0};
  const auto state = ts::prepare(f, .5f, .13f, -.07f, .3f, 0);
  // Existing screen slopes include C/f once. Body sensor position is invariant.
  for (float qx : {-.3f, 0.f, .3f})
    for (float qy : {-.2f, 0.f, .2f}) {
      const auto baseline = ts::sensor(state, qx, qy);
      const auto moved = ts::add(center, ts::sensor(state, qx + center.x / f, qy + center.y / f));
      check(std::abs(moved.x - baseline.x) < 2e-9 && std::abs(moved.y - baseline.y) < 2e-9,
            "physical lens shift preserves fixed body sensor rectangle");
      const auto ray = ts::sample(state, qx + center.x / f, qy + center.y / f, 0, 0);
      const auto origin = ts::add(center, ray.origin);
      check(std::abs(origin.x - center.x) < 1e-9 && std::abs(origin.y - center.y) < 1e-9,
            "shifted chief rays originate at translated lens centre");
      const double z = .7;
      const auto point = ts::add(origin, ts::mul(ray.direction, float(z / ray.direction.z)));
      const double invx = (point.x - center.x) / point.z * (state.sensor_distance / f) -
                          center.x / f;
      const double invy = (point.y - center.y) / point.z * (state.sensor_distance / f) -
                          center.y / f;
      check(std::abs(invx - qx) < 2e-7 && std::abs(invy - qy) < 2e-7,
            "physical shift inverse projection has no double framing offset");
    }
  for (const ts::Vec target_body :
       {ts::Vec{.03f, -.02f, .5f}, ts::Vec{-.04f, .03f, .8f}, ts::Vec{.05f, .7f, .5f}})
  {
    const auto target = ts::add(target_body, ts::mul(center, -1));
    const auto focused = ts::focus_at(state, target);
    const auto plane = ts::add(focused.normal, ts::Vec{0, 0, -f / focused.sensor_distance});
    check(std::abs(ts::dot(plane, target) - f) < 1e-7,
          "offaxis focus object satisfies sharp plane");
    const auto p = ts::mul(target, 1.f / (1.f - ts::dot(focused.normal, target) / f));
    check(std::abs(p.z + focused.sensor_distance) < 1e-7, "focus object maps onto fixed sensor Z");
    for (float a : {-.008f, 0.f, .008f}) {
      const auto ray = ts::sample(focused, -p.x / f, -p.y / f, a, .003f);
      const auto hit = ts::add(
          ray.origin, ts::mul(ray.direction, (target.z - ray.origin.z) / ray.direction.z));
      check(std::sqrt(ts::dot(ts::add(hit, ts::mul(target, -1)),
                              ts::add(hit, ts::mul(target, -1)))) < 2e-6,
            "all tilted aperture samples meet offaxis focus object");
    }
  }
}

void infinite_and_virtual_conjugates()
{
  Parameters p;
  p.focus_distance = std::numeric_limits<double>::infinity();
  for (double tilt : {0., .14}) {
    p.tilt = tilt;
    const ThinLens camera(p);
    const auto state = ts::prepare(
        float(p.focal_length), std::numeric_limits<float>::infinity(), float(tilt), 0, 0, 0);
    for (double y : {-1., -1e-7, 0., 1e-7, 1.}) {
      compare_ray(camera, state, .4, y, .7, -.2);
      const auto q = camera.sensor_point(.4, y);
      const auto a = ts::sample(
          state, float(-q.x / p.focal_length), float(q.y / p.focal_length), 0, 0);
      const auto b = ts::sample(
          state, float(-q.x / p.focal_length), float(q.y / p.focal_length), .005f, .001f);
      if (y == 0 || tilt == 0)
        check(length(reflect(a.direction) - reflect(b.direction)) < 2e-7,
              "native infinite conjugate rays parallel across aperture");
    }
  }
}

void differential_and_breathing()
{
  Parameters p;
  p.tilt = .13;
  p.swing = -.07;
  p.axis_rotation = .3;
  p.shift_x = .002;
  ThinLens c(p);
  const auto s = ts::prepare(float(p.focal_length),
                             float(p.focus_distance),
                             float(p.tilt),
                             float(p.swing),
                             float(p.axis_rotation),
                             0);
  // Exact same-aperture neighboring samples used by native ray footprints.
  const double dx = 2. / 640, dy = 2. / 360;
  const double x = .31, y = -.42, ax = .2, ay = -.7;
  auto native = [&](double u, double v) {
    const auto sensor = c.sensor_point(u, v);
    return ts::clip_near(ts::sample(s,
                                    float(-sensor.x / p.focal_length),
                                    float(sensor.y / p.focal_length),
                                    float(ax * p.aperture_radius),
                                    float(-ay * p.aperture_radius)),
                         .1f);
  };
  const auto n = native(x, y);
  const auto ref = c.ray_at(x, y, ax, ay);
  for (const auto step : {Vec3{dx, 0, 0}, Vec3{0, dy, 0}}) {
    const auto nn = native(x + step.x, y + step.y);
    const auto rr = c.ray_at(x + step.x, y + step.y, ax, ay);
    check(length((reflect(nn.direction) - reflect(n.direction)) - (rr.direction - ref.direction)) <
              4e-7,
          "neighboring physical direction differential");
    check(length((reflect(nn.origin) - reflect(n.origin)) - (clipped(rr, .1) - clipped(ref, .1))) <
              1e-7,
          "neighboring clipped origin differential");
  }
  for (double focus : {.15, .5, 5.}) {
    const auto state = ts::prepare(.05f, float(focus), 0, 0, 0, 0);
    const auto r = ts::sample(state, .36f, 0, 0, 0);
    check(std::abs(r.direction.x / r.direction.z - .36 * .05 / state.sensor_distance) < 1e-7,
          "chief ray physical breathing");
    const double inverted = (r.direction.x / r.direction.z) * (state.sensor_distance / .05);
    check(std::abs(inverted - .36) < 1e-7, "inverse chief projection b/f");
  }
}
}  // namespace
int main()
{
  try {
    ray_matrix();
    differential_and_breathing();
    physical_shift_and_focus_object();
    infinite_and_virtual_conjugates();
    std::cout << "PASS: " << checks
              << " native float checks; max direction error=" << max_direction_error
              << " max aperture origin error=" << max_origin_error << " m\n";
  }
  catch (const std::exception &e) {
    std::cerr << "FAIL after " << checks << ": " << e.what() << '\n';
    return 1;
  }
}
