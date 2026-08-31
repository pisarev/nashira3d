{ ************************************************************************** }
{                                                                            }
{ CamProbe                                                                   }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

program CamProbe;

{ A camera probe WITHOUT graphics.

  The camera is pure arithmetic, and checking it through a frame would mean
  measuring the graphics card, the shaders and the fit to the box along with
  it. What is checked here is exactly the statements that were agreed in
  review:

    4.4.1  the height does NOT change with the elevation;
    4.4.2  the elevation touches nothing but the direction, and the wheel
           nothing but the height;
    4.4.3  zero is crossed: 2001 positions from +1 to -1, including an exact
           zero, and not a single forbidden value;
    4.4.4  there is no hidden clamp: camera_z - z0 equals H to Double precision
           at twenty-one values, down to 1e-10;
    plus   the region is finite at any position, including a ray along the
           plane and a camera IN the plane.
}

{$mode objfpc}{$H+}
{$APPTYPE CONSOLE}

uses
  SysUtils, Math, nsh_camera, nsh_ticks;

const
  { TYPED ON PURPOSE, and that is not decoration.

    FPC carries out a comparison between a Double field and an untyped real
    constant in Extended, and Extended takes eight bytes on Win64 and ten on
    x86_64 Linux. Because of that, one and the same sound camera produced 1000
    deviations out of 1000 on the very first run under Linux, the worst being
    3.90312782094781596243E-017 - a quantity SMALLER than the step of a Double,
    that is, not a deviation at all but a different width of the intermediate
    type.

    The comparisons below stay EXACT, with no tolerance: typing removes a
    property of the measuring environment, not the strictness of the check. A
    tolerance is forbidden here - exact equality is the very subject of 4.4.1
    and 4.4.2. }
  ProbeH  : Double = 3.169;
  ProbeCx : Double = 0.3;
  ProbeCy : Double = -0.7;

var
  Ok  : LongInt = 0;
  Bad : LongInt = 0;

procedure Check(const Name: string; Cond: Boolean; const Got: string);
begin
  if Cond then
  begin
    Inc(Ok);
    Writeln('  ok   ', Name:56, '  ', Got);
  end
  else begin
    Inc(Bad);
    Writeln('  FAIL ', Name:56, '  ', Got);
  end;
end;

function MakeCam(H: Double): TCam;
begin
  Result.Cx := ProbeCx;
  Result.Cy := ProbeCy;
  Result.H := H;
  Result.Az := 0.9;
  Result.El := 0.45;
  Result.Fov := 0.9;
end;

var
  C     : TCam;
  E     : TVec3;
  Rg    : TRegion;
  I     : LongInt;
  Drift : LongInt;
  Worst : Double;
  Hv    : Double;
  Bads  : LongInt;
  Cnt   : LongInt;
  Lines : TDoubleArray;
  Rays  : array[0..3] of TVec3;
  Seed  : LongInt;
  Denom : Double;
  Tmp   : Double;

  { A generator of its own rather than Random: the probe has to produce the
    same numbers on any machine and in any order of running. }
  function NextRnd: Double;
  begin
    Seed := (Seed * 1103515245 + 12345) and $3FFFFFFF;
    Result := Seed / 1073741824.0;
  end;

begin
  Writeln('THE CAMERA AS A STANDING POINT');

  { 4.4.1: the height does not change with the elevation }
  Seed := 12345;
  C := MakeCam(ProbeH);
  Drift := 0;
  Worst := 0;
  for I := 1 to 1000 do
  begin
    C.Az := NextRnd * 2 * Pi;
    C.El := 0.02 + NextRnd * 1.5;
    E := CamEye(C, 0);
    if Abs(E.Z - ProbeH) > Worst then Worst := Abs(E.Z - ProbeH);
    if E.Z <> ProbeH then Inc(Drift);
  end;
  Check('4.4.1 a thousand elevations: the height did not move', Drift = 0,
        Format('deviations %d, worst %.3e', [Drift, Worst]));

  { 4.4.2: the elevation does not move the standing point }
  Drift := 0;
  for I := 1 to 500 do
  begin
    C.Az := NextRnd * 2 * Pi;
    C.El := 0.02 + NextRnd * 1.5;
    E := CamEye(C, 0);
    if (E.X <> ProbeCx) or (E.Y <> ProbeCy) then Inc(Drift);
  end;
  Check('4.4.2 the elevation did not move the standing point', Drift = 0,
        Format('deviations %d', [Drift]));

  { The wheel changes only the height: the direction has to stay as it was. }
  C := MakeCam(2.0);
  E := CamForward(C);
  Drift := 0;
  for I := -50 to 50 do
  begin
    C.H := I * 0.04;
    if (CamForward(C).X <> E.X) or (CamForward(C).Y <> E.Y) or
      (CamForward(C).Z <> E.Z) then Inc(Drift);
  end;
  Check('4.4.2 the wheel did not touch the direction of view', Drift = 0,
        Format('deviations %d out of 101', [Drift]));

  { 4.4.3: crossing zero }
  { 2001 positions from +1 to -1 inclusive, a step of exactly 0.001, and zero
    lands exactly: at I = 1000 the expression (1000 - I) * 0.001 gives a
    machine zero. }
  Bads := 0;
  Drift := 0;
  for I := 0 to 2000 do
  begin
    Hv := (1000 - I) * 0.001;
    C := MakeCam(Hv);
    E := CamEye(C, 0);
    if IsNan(E.Z) or IsInfinite(E.Z) then Inc(Bads);
    Rg := CamRegion(C, 1.6, 0, -0.8, 0.8, 0);
    if IsNan(Rg.X0) or IsNan(Rg.X1) or IsNan(Rg.Y0) or IsNan(Rg.Y1) or
      IsInfinite(Rg.X0) or IsInfinite(Rg.X1) or
      IsInfinite(Rg.Y0) or IsInfinite(Rg.Y1) then Inc(Bads);
    if not Rg.Ok then Inc(Drift);
  end;
  Check('4.4.3 2001 positions: neither NaN nor Inf', Bads = 0, Format('spoiled %d', [Bads]));
  { An empty region is NOT a refusal but the agreed behaviour: a camera that
    has gone below the slab and still looks downwards is looking AWAY from the
    surface. To see it from below, the elevation is raised by hand; otherwise
    the wheel would secretly change the direction too. There have to be exactly
    as many empty ones as there are positions below the slab: H from -0.801 to
    -1.000 with a slab half-thickness of 0.8 is 200 out of 2001. }
  Check('4.4.3 empty exactly where the camera went below the slab', Drift = 200,
        Format('empty %d out of 2001', [Drift]));
  { The exact zero, separately and by name: it is the very thing this was
    written for. }
  C := MakeCam(0.0);
  E := CamEye(C, 0);
  Rg := CamRegion(C, 1.6, 0, -0.8, 0.8, 0);
  Check('4.4.3 camera IN the plane: the height is exactly zero', E.Z = 0.0, Format('%.17g', [E.Z]));
  Check('4.4.3 camera IN the plane: the region is finite',
        Rg.Ok and (not IsInfinite(Rg.X1 - Rg.X0)) and (Rg.X1 >= Rg.X0),
        Format('x %.3f..%.3f, y %.3f..%.3f', [Rg.X0, Rg.X1, Rg.Y0, Rg.Y1]));

  { 4.4.4: there is no hidden clamp }
  Bads := 0;
  Worst := 0;
  for I := 0 to 20 do
  begin
    if I = 20 then
      Hv := 0.0
    else begin
      Hv := Power(10.0, -(1 + I div 2));
      if Odd(I) then Hv := -Hv;
    end;
    C := MakeCam(Hv);
    E := CamEye(C, 0);
    if E.Z - 0 <> Hv then
    begin
      Inc(Bads);
      if Abs(E.Z - Hv) > Worst then Worst := Abs(E.Z - Hv);
    end;
  end;
  Check('4.4.4 21 values of H: camera_z - z0 equals H exactly', Bads = 0,
        Format('mismatches %d, worst %.3e', [Bads, Worst]));

  { a ray along the plane }
  { An elevation of exactly zero: the central ray runs along the slab, and
    there must be no division by its Z. This is the case the extent limit is
    named explicitly for. }
  C := MakeCam(0.0);
  C.El := 0;
  Rg := CamRegion(C, 1.6, 0, 0, 0, 0);
  Check('a ray along the plane gave no infinity',
        Rg.Ok and (not IsInfinite(Rg.X1)) and (not IsNan(Rg.X1)),
        Format('x %.2f..%.2f', [Rg.X0, Rg.X1]));
  C := MakeCam(2.0);
  C.El := -0.6;   { looking UP: the plane ahead is not crossed at all }
  Rg := CamRegion(C, 1.6, 0, -0.8, 0.8, 0);
  Check('a look above the horizon: empty and finite, no infinities',
        (not Rg.Ok) and (not IsInfinite(Rg.X1 - Rg.X0)) and
    (not IsNan(Rg.X1 - Rg.X0)),
        Format('region found: %s', [BoolToStr(Rg.Ok, True)]));

  { the extent is named explicitly and is obeyed }
  { The extent bites on a ray running ALONG the slab, not across it: a
    crosswise ray runs into the far face of the slab even without a limit. So
    the camera is placed INSIDE the slab and almost horizontally - the first
    version of this probe missed that and measured a case the limit had nothing
    to do with: 3.4 against 3.4. }
  { The elevation is taken to be HALF the field of view: then the upper ray of
    the frustum runs exactly along the slab and goes all the way to the limit.
    At an elevation of 0.02 all four rays turned out steeper than the slab and
    left it within a unit and a half - a limit of five was of no use to them,
    and the probe measured a case it had nothing to do with. }
  C := MakeCam(0.0);
  C.El := C.Fov / 2;
  Rg := CamRegion(C, 1.6, 0, -0.5, 0.5, 0);
  Worst := Rg.X1 - Rg.X0;
  Rg := CamRegion(C, 1.6, 0, -0.5, 0.5, 5.0);
  Check('an explicit extent narrows the region', (Rg.X1 - Rg.X0) < Worst * 0.9,
        Format('was %.1f, became %.1f', [Worst, Rg.X1 - Rg.X0]));

  { the height governs the coverage }
  C := MakeCam(1.0);
  Rg := CamRegion(C, 1.6, 0, -0.3, 0.3, 0);
  Worst := Rg.X1 - Rg.X0;
  C.H := 4.0;
  Rg := CamRegion(C, 1.6, 0, -0.3, 0.3, 0);
  Denom := Rg.X1 - Rg.X0;
  Check('a height four times greater gave a larger region', Denom > Worst,
        Format('%.2f against %.2f', [Denom, Worst]));
  { From below - with the elevation RAISED: under the slab a downward look
    faces away from the surface, and the elevation is raised by hand. That is
    exactly what was agreed. The coverage is of the same size: the coordinate
    system is not turned over, the point of view is what changes. }
  C.H := -4.0;
  C.El := -C.El;
  Rg := CamRegion(C, 1.6, 0, -0.3, 0.3, 0);
  Check('from below with the elevation raised, the coverage is the same size',
        Abs((Rg.X1 - Rg.X0) - Denom) < Denom * 1E-9,
        Format('%.4f against %.4f', [Rg.X1 - Rg.X0, Denom]));

  { the rays are of unit length }
  C := MakeCam(2.0);
  CamCorners(C, 1.6, Rays);
  Bads := 0;
  for I := 0 to 3 do
    if Abs(Sqrt(Rays[I].X * Rays[I].X + Rays[I].Y * Rays[I].Y +
      Rays[I].Z * Rays[I].Z) - 1) > 1E-12 then Inc(Bads);
  Check('four rays of unit length', Bads = 0, Format('spoiled %d', [Bads]));

  { THE TICK STEP: only 1, 2 or 5 }
  { A label on the grid is a promise that the line stands on a ROUND number. A
    step of 0.37 breaks that promise: the neighbouring labels would be 0.37 and
    0.74, and nothing can be counted by them. The rule is checked by sweeping
    the whole working range of magnitudes, not on three convenient numbers. }
  Bads := 0;
  Worst := 0;
  for I := 0 to 9000 do
  begin
    Hv := Power(10.0, -6.0 + I * 12.0 / 9000.0);
    Denom := NiceStep(Hv);
    if Denom <= 0 then
    begin
      Inc(Bads); Continue;
    end;
    { the mantissa: the step divided by ten to the power of its order }
    Tmp := Denom / Power(10.0, Floor(Log10(Denom) + 1E-9));
    if (Abs(Tmp - 1) > 1E-9) and (Abs(Tmp - 2) > 1E-9) and (Abs(Tmp - 5) > 1E-9) then
    begin
      Inc(Bads);
      if Abs(Tmp) > Worst then Worst := Abs(Tmp);
    end;
  end;
  Check('the tick step is always 1, 2 or 5 times a power of ten', Bads = 0,
        Format('breaches %d out of 9001, worst mantissa %.4f', [Bads, Worst]));

  { Thinning the series does not lead out of the series. }
  Bads := 0;
  for I := 0 to 200 do
  begin
    Hv := Power(10.0, -3.0 + I * 6.0 / 200.0);
    Denom := StepUp(NiceStep(Hv));
    Tmp := Denom / Power(10.0, Floor(Log10(Denom) + 1E-9));
    if (Abs(Tmp - 1) > 1E-9) and (Abs(Tmp - 2) > 1E-9) and (Abs(Tmp - 5) > 1E-9) then
      Inc(Bads);
  end;
  Check('thinning stays inside the 1-2-5 series', Bads = 0,
        Format('breaches %d out of 201', [Bads]));
  { The chosen step is close to the one asked for: no more than twice either
    way. }
  Bads := 0;
  for I := 0 to 2000 do
  begin
    Hv := Power(10.0, -4.0 + I * 8.0 / 2000.0);
    Denom := NiceStep(Hv);
    if (Denom > Hv * 2.0000001) or (Denom < Hv / 2.0000001) then Inc(Bads);
  end;
  Check('the step is never more than twice away from the one asked for', Bads = 0,
        Format('breaches %d out of 2001', [Bads]));

  { PLACING THE SAMPLING LINES BY SCREEN DENSITY }
  { The contract: the lines cover the segment exactly, increase strictly, and
    stand DENSER where it is nearer the camera. The last of these is the whole
    point: there are exactly as many nodes as the quality gave, and spending
    them on the horizon, where the entire distance fits into a dozen rows of
    the frame, is not allowed. }
  C.Cx := 0;
  C.Cy := -3;
  C.H := 1.5;
  C.Az := Pi / 2;
  C.El := 0.30;
  C.Fov := 0.9;
  CamAxisLines(C, -20, 5, 0, 0, False, 64, Lines);
  Check('as many lines as were asked for', Length(Lines) = 64, Format('%d', [Length(Lines)]));
  Check('the ends of the segment stand exactly', (Lines[0] = -20) and (Lines[63] = 5), '');
  Bads := 0;
  for I := 1 to High(Lines) do
    if not (Lines[I] > Lines[I - 1]) then Inc(Bads);
  Check('strictly increasing', Bads = 0, Format('breaches %d', [Bads]));
  { The half nearer the camera has to get MORE lines than the far one. The
    camera stands at y = -3 and looks towards decreasing y, so the near half is
    the upper part of the segment. }
  Cnt := 0;
  for I := 0 to High(Lines) do
    if Lines[I] > -7.5 then Inc(Cnt);
  Check('the near half got more lines', Cnt > 40,
        Format('%d out of 64 in the near quarter of the segment', [Cnt]));
  { The gaps grow WITH DISTANCE rather than at random. Strict monotonicity is
    not required - the weights are computed numerically - but an overwhelming
    majority is. }
  { The gaps are counted ONLY in the visible part: behind the camera their
    order means nothing, and the weight there is deliberately almost zero. The
    camera stands at y = -3 and looks towards decreasing y. }
  { The lines run in increasing order, that is FROM THE DISTANCE TOWARDS THE
    CAMERA: the camera stands at y = -3, looks towards decreasing y, and the
    visible part is the beginning of the segment. So as the index grows the
    gaps have to NARROW. The sign in this check was the wrong way round at
    first, and it reported "39 breaches out of 39" - meaning every single gap
    behaved as it should. }
  Bads := 0;
  Cnt := 0;
  for I := 1 to High(Lines) - 1 do
    if Lines[I + 1] < -3.5 then
    begin
      Inc(Cnt);
      if (Lines[I + 1] - Lines[I]) > (Lines[I] - Lines[I - 1]) + 1E-12 then
        Inc(Bads);
    end;
  Check('in the visible part the gaps narrow towards the camera', Bads <= 1,
        Format('widenings %d out of %d', [Bads, Cnt]));
  { The other side of it: behind the camera noticeably fewer nodes are spent.
    Without this the check above would also pass for a placement that gives the
    invisible part as much as the visible one.

    The number is named as a measure rather than a round threshold: behind lie
    8 units out of 25, and an even placement would have put 20 lines out of 64
    there. }
  Cnt := 0;
  for I := 0 to High(Lines) do
    if Lines[I] > -3 then Inc(Cnt);
  Check('behind the camera there are half as many lines as an even placement',
        Cnt <= 12, Format('%d out of 64, an even one would give 20', [Cnt]));
  { A vertical look from a great height: perspective barely works, and the
    placement has to come out almost even. This is the other side of it -
    without it the check above would also pass for a placement that always
    crowds the lines towards one end. }
  C.Cx := 0;
  C.Cy := 0;
  C.H := 400;
  C.Az := Pi / 2;
  C.El := Pi / 2 - 0.01;
  CamAxisLines(C, -10, 10, 0, 0, False, 64, Lines);
  Worst := 0;
  for I := 1 to High(Lines) do
    Worst := Max(Worst, Abs((Lines[I] - Lines[I - 1]) - 20 / 63));
  Check('from above and far away the placement is almost even', Worst < 0.02,
        Format('%.5f against a step of %.5f', [Worst, 20 / 63]));
  { The degenerate cases: an empty segment, few lines, the camera IN the plane.
    Everything has to stay finite and meaningful. }
  CamAxisLines(C, 5, 5, 0, 0, True, 16, Lines);
  Bads := 0;
  for I := 0 to High(Lines) do
    if IsNan(Lines[I]) or IsInfinite(Lines[I]) then Inc(Bads);
  Check('a zero-length segment gives no infinities', Bads = 0, '');
  C.H := 0;
  C.El := 0;
  CamAxisLines(C, -5, 5, 0, 0, False, 32, Lines);
  Bads := 0;
  for I := 0 to High(Lines) do
    if IsNan(Lines[I]) or IsInfinite(Lines[I]) then Inc(Bads);
  for I := 1 to High(Lines) do
    if not (Lines[I] > Lines[I - 1]) then Inc(Bads);
  Check('camera IN the plane: the lines are finite and increasing', Bads = 0,
        Format('breaches %d', [Bads]));
  Writeln;
  Writeln('checks: ', Ok + Bad, ', failures: ', Bad);
  if Bad > 0 then Halt(1);
end.
