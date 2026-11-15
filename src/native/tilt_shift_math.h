/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

/* Shared scalar float implementation: no STL, allocation, exceptions or Blender
 * types. Lengths are metres; frame is Cycles (+X right, +Y up, +Z scene-going).
 * Caller supplies sqrtf/sinf/cosf and a device-compatible inline qualifier. */
#ifndef TILT_SHIFT_DEVICE
#  define TILT_SHIFT_DEVICE inline
#  define TILT_SHIFT_LOCAL_QUALIFIER
#endif

namespace tilt_shift_native {
struct Vec {
  float x, y, z;
};
struct State {
  Vec normal, aperture_x, aperture_y;
  float focal_length, sensor_distance, circle_radius;
};
struct Ray {
  Vec origin, direction;
  float weight;
};

TILT_SHIFT_DEVICE Vec add(Vec a, Vec b)
{
  return {a.x + b.x, a.y + b.y, a.z + b.z};
}

TILT_SHIFT_DEVICE Vec mul(Vec a, float b)
{
  return {a.x * b, a.y * b, a.z * b};
}

TILT_SHIFT_DEVICE float dot(Vec a, Vec b)
{
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

TILT_SHIFT_DEVICE Vec normalize(Vec a)
{
  return mul(a, 1.0f / sqrtf(dot(a, a)));
}

/* Rz(axis) Ry(swing) Rx(tilt) in the reference's Y-down frame, followed by
 * S=diag(1,-1,1). Reflection reverses basis handedness; do not rebuild ey by
 * cross product. Basis Y points down at zero angle. */
TILT_SHIFT_DEVICE State
prepare(float f, float focus, float tilt, float swing, float axis, float circle_radius)
{
  const float ct = cosf(tilt), st = sinf(tilt);
  const float cs = cosf(swing), ss = sinf(swing);
  const float ca = cosf(axis), sa = sinf(axis);
  State s;
  s.normal = {ca * ss * ct + sa * st, -sa * ss * ct + ca * st, cs * ct};
  s.aperture_x = {ca * cs, -sa * cs, -ss};
  s.aperture_y = {ca * ss * st - sa * ct, -sa * ss * st - ca * ct, cs * st};
  s.focal_length = f;
  s.sensor_distance = f / (s.normal.z - f / focus);
  s.circle_radius = circle_radius;
  return s;
}

/* Focus object coordinates are relative to the translated lens centre. This
 * follows directly from (n-(f/b)k).Q=f and keeps off-axis targets sharp. */
TILT_SHIFT_DEVICE State focus_at(State s, Vec target)
{
  s.sensor_distance = s.focal_length * target.z / (dot(s.normal, target) - s.focal_length);
  return s;
}

/* q is the legacy virtual-screen slope q.xy/q.z. Inversion maps raster to
 * physical sensor; keeping nominal f here preserves sensor fit and shift. */
TILT_SHIFT_DEVICE Vec sensor(State s, float qx, float qy)
{
  return {-s.focal_length * qx, -s.focal_length * qy, -s.sensor_distance};
}

TILT_SHIFT_DEVICE bool covered(State s, Vec p)
{
  if (s.circle_radius == 0.0f) {
    return true; /* Explicit unbounded encoding. */
  }
  const Vec rear = add(mul(p, -s.focal_length / dot(s.normal, p)), mul(s.normal, s.focal_length));
  return dot(rear, rear) <= s.circle_radius * s.circle_radius;
}

/* Aperture coordinates already contain radius, polygon and anamorphic scaling.
 * Minus ey preserves the existing Cycles bokeh rotation at zero movements. */
TILT_SHIFT_DEVICE Ray sample(State s, float qx, float qy, float ax, float ay)
{
  const Vec p = sensor(s, qx, qy);
  const Vec a = add(mul(s.aperture_x, ax), mul(s.aperture_y, -ay));
  const float h = 1.0f + dot(s.normal, p) / s.focal_length;
  return {a, normalize(add(mul(a, h), mul(p, -1.0f))), covered(s, p) ? 1.0f : 0.0f};
}

/* Intersect camera-Z clip planes after sampling the genuinely tilted aperture.
 * Validation guarantees origin.z<near and direction.z>0. */
TILT_SHIFT_DEVICE Ray clip_near(Ray r, float nearclip)
{
  r.origin = add(r.origin, mul(r.direction, (nearclip - r.origin.z) / r.direction.z));
  return r;
}
}  // namespace tilt_shift_native

#ifdef TILT_SHIFT_LOCAL_QUALIFIER
#  undef TILT_SHIFT_DEVICE
#  undef TILT_SHIFT_LOCAL_QUALIFIER
#endif
