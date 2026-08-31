{ ************************************************************************** }
{                                                                            }
{ nsh_camera                                                                 }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

unit nsh_camera;

{$mode objfpc}{$H+}

interface

type
  TDoubleArray = array of Double;

  TCam = record
    Cx, Cy : Double;
    H      : Double;
    Az, El : Double;
    Fov    : Double;
  end;

  TVec3 = record
    X, Y, Z : Double;
  end;

  TRegion = record
    X0, X1, Y0, Y1 : Double;
    Ok             : Boolean;
  end;

function CamEye(const C: TCam; Z0: Double): TVec3;

function CamForward(const C: TCam): TVec3;

function CamRay(const C: TCam; Aspect, Sx, Sy: Double): TVec3;

procedure CamCorners(const C: TCam; Aspect: Double; out R: array of TVec3);

function CamFar(const C: TCam; Zmin, Zmax, MaxExtent: Double): Double;

function CamRegion(const C: TCam; Aspect, Z0, Zmin, Zmax, MaxExtent: Double): TRegion;

procedure CamAxisLines(const C: TCam; A0, A1, Other, Zc: Double; AlongX: Boolean; N: LongInt;
  out Lines: TDoubleArray);

implementation

uses
  Math;

const
  FAR_IN_HEIGHTS = 8.0;

function CamEye(const C: TCam; Z0: Double): TVec3;
begin
  Result.X := C.Cx;
  Result.Y := C.Cy;
  Result.Z := Z0 + C.H;
end;

function CamForward(const C: TCam): TVec3;
var
  Cs, Sn: Double;
begin
  Cs := Cos(C.El);
  Sn := Sin(C.El);
  Result.X := -Cs * Cos(C.Az);
  Result.Y := -Cs * Sin(C.Az);
  Result.Z := -Sn;
end;

function CamRay(const C: TCam; Aspect, Sx, Sy: Double): TVec3;
var
  F, Rt, Up: TVec3;
  Tv, Th, L: Double;
begin
  F := CamForward(C);
  Rt.X := -Sin(C.Az);
  Rt.Y := Cos(C.Az);
  Rt.Z := 0;
  Up.X := Rt.Y * F.Z - Rt.Z * F.Y;
  Up.Y := Rt.Z * F.X - Rt.X * F.Z;
  Up.Z := Rt.X * F.Y - Rt.Y * F.X;
  Tv := Tan(C.Fov / 2);
  Th := Tv * Aspect;
  Result.X := F.X + Up.X * Tv * Sy + Rt.X * Th * Sx;
  Result.Y := F.Y + Up.Y * Tv * Sy + Rt.Y * Th * Sx;
  Result.Z := F.Z + Up.Z * Tv * Sy + Rt.Z * Th * Sx;
  L := Sqrt(Result.X * Result.X + Result.Y * Result.Y + Result.Z * Result.Z);
  if L < 1E-300 then L := 1;
  Result.X := Result.X / L;
  Result.Y := Result.Y / L;
  Result.Z := Result.Z / L;
end;

procedure CamCorners(const C: TCam; Aspect: Double; out R: array of TVec3);
var
  I, Sx, Sy: LongInt;
begin
  if Length(R) < 4 then Exit;
  for I := 0 to 3 do
  begin
    if (I and 1) = 0 then
      Sx := -1
    else
      Sx := 1;
    if (I and 2) = 0 then
      Sy := 1
    else
      Sy := -1;
    R[I] := CamRay(C, Aspect, Sx, Sy);
  end;
end;

function CamFar(const C: TCam; Zmin, Zmax, MaxExtent: Double): Double;
var
  Thick: Double;
begin
  if (MaxExtent > 0) and (not IsInfinite(MaxExtent)) and (not IsNan(MaxExtent)) then
    Exit(MaxExtent);
  Thick := Abs(Zmax - Zmin);
  if IsNan(Thick) or IsInfinite(Thick) then Thick := 0;
  Result := FAR_IN_HEIGHTS * (Abs(C.H) + Thick);
  if Result < 1 then Result := 1;
end;

function CamRegion(const C: TCam; Aspect, Z0, Zmin, Zmax, MaxExtent: Double): TRegion;
const
  EDGE_STEPS = 24;
var
  Eye, Ray: TVec3;
  Far_, Lo, Hi, T1, T2, Tmp, Sx, Sy: Double;
  I, Side: LongInt;
  Zl, Zh: Double;

  procedure Take(Px, Py: Double);
  begin
    if IsNan(Px) or IsNan(Py) or IsInfinite(Px) or IsInfinite(Py) then Exit;
    if not Result.Ok then
    begin
      Result.X0 := Px;
      Result.X1 := Px;
      Result.Y0 := Py;
      Result.Y1 := Py;
      Result.Ok := True;
      Exit;
    end;
    if Px < Result.X0 then Result.X0 := Px;
    if Px > Result.X1 then Result.X1 := Px;
    if Py < Result.Y0 then Result.Y0 := Py;
    if Py > Result.Y1 then Result.Y1 := Py;
  end;

  procedure Sweep(RayDir: TVec3);
  begin
    if Abs(RayDir.Z) < 1E-12 then
    begin
      if (Eye.Z < Zl) or (Eye.Z > Zh) then Exit;
      Lo := 0;
      Hi := Far_;
    end
    else begin
      T1 := (Zl - Eye.Z) / RayDir.Z;
      T2 := (Zh - Eye.Z) / RayDir.Z;
      if T1 > T2 then
      begin
        Tmp := T1;
        T1 := T2;
        T2 := Tmp;
      end;
      if T2 < 0 then Exit;
      Lo := Min(Max(T1, 0), Far_);
      Hi := Min(Max(T2, 0), Far_);
    end;
    Take(Eye.X + RayDir.X * Lo, Eye.Y + RayDir.Y * Lo);
    Take(Eye.X + RayDir.X * Hi, Eye.Y + RayDir.Y * Hi);
  end;

begin
  Result.X0 := 0;
  Result.X1 := 0;
  Result.Y0 := 0;
  Result.Y1 := 0;
  Result.Ok := False;
  Zl := Min(Zmin, Zmax);
  Zh := Max(Zmin, Zmax);
  if IsNan(Zl) or IsNan(Zh) or IsInfinite(Zl) or IsInfinite(Zh) then Exit;
  Eye := CamEye(C, Z0);
  Far_ := CamFar(C, Zl, Zh, MaxExtent);
  if (Eye.Z >= Zl) and (Eye.Z <= Zh) then Take(Eye.X, Eye.Y);
  for Side := 0 to 3 do
    for I := 0 to EDGE_STEPS do
    begin
      Tmp := -1 + 2 * I / EDGE_STEPS;
      case Side of
        0:
        begin
          Sx := Tmp;
          Sy := 1;
        end;
        1:
        begin
          Sx := Tmp;
          Sy := -1;
        end;
        2:
        begin
          Sx := -1;
          Sy := Tmp;
        end;
      else begin
        Sx := 1;
        Sy := Tmp;
      end;
      end;
      Ray := CamRay(C, Aspect, Sx, Sy);
      Sweep(Ray);
    end;
end;

procedure CamAxisLines(const C: TCam; A0, A1, Other, Zc: Double; AlongX: Boolean; N: LongInt;
  out Lines: TDoubleArray);
const
  PROBES = 512;
var
  E: TVec3;
  W: array[0..PROBES] of Double;
  Cum: array[0..PROBES] of Double;
  I, K, J: LongInt;
  Da, A, Vx, Vy, Vz, L, Dot_, Px, Py, Pz, Perp, Target, T: Double;
  FX, FY, FZ: Double;
  Fwd: TVec3;
  Uniformly: Boolean;

  procedure PutUniform;
  var Q: LongInt;
  begin
    SetLength(Lines, N);
    for Q := 0 to N - 1 do
      Lines[Q] := A0 + (A1 - A0) * Q / (N - 1);
  end;

begin
  if N < 2 then
  begin
    SetLength(Lines, 0); Exit;
  end;
  if (A1 - A0) <= 0 then
  begin
    PutUniform; Exit;
  end;
  E := CamEye(C, Zc);
  Fwd := CamForward(C);
  FX := Fwd.X;
  FY := Fwd.Y;
  FZ := Fwd.Z;
  Da := (A1 - A0) / PROBES;
  for I := 0 to PROBES do
  begin
    A := A0 + Da * I;
    if AlongX then
    begin
      Px := A;
      Py := Other;
    end
              else begin
                Px := Other;
                Py := A;
              end;
    Pz := Zc;
    Vx := Px - E.X;
    Vy := Py - E.Y;
    Vz := Pz - E.Z;
    L := Sqrt(Vx * Vx + Vy * Vy + Vz * Vz);
    if L < 1E-9 then
    begin
      W[I] := 0;
      Continue;
    end;
    Vx := Vx / L;
    Vy := Vy / L;
    Vz := Vz / L;
    if AlongX then
      Dot_ := Vx
    else
      Dot_ := Vy;
    Perp := 1 - Dot_ * Dot_;
    if Perp < 0 then Perp := 0;
    W[I] := Sqrt(Perp) / L;
    if (Vx * FX + Vy * FY + Vz * FZ) <= 0 then W[I] := W[I] * 0.01;
    if IsNan(W[I]) or IsInfinite(W[I]) then W[I] := 0;
  end;
  Cum[0] := 0;
  for I := 1 to PROBES do
    Cum[I] := Cum[I - 1] + (W[I] + W[I - 1]) * 0.5 * Da;
  Uniformly := (Cum[PROBES] <= 0) or IsNan(Cum[PROBES]) or IsInfinite(Cum[PROBES]);
  if Uniformly then
  begin
    PutUniform; Exit;
  end;
  SetLength(Lines, N);
  Lines[0] := A0;
  Lines[N - 1] := A1;
  J := 0;
  for K := 1 to N - 2 do
  begin
    Target := Cum[PROBES] * K / (N - 1);
    while (J < PROBES) and (Cum[J + 1] < Target) do Inc(J);
    if J >= PROBES then
      Lines[K] := A1
    else begin
      T := Cum[J + 1] - Cum[J];
      if T <= 0 then
        T := 0
      else
        T := (Target - Cum[J]) / T;
      Lines[K] := A0 + Da * (J + T);
    end;
    if Lines[K] <= Lines[K - 1] then
      Lines[K] := Lines[K - 1] + (A1 - A0) * 1E-6;
  end;
  if Lines[N - 1] <= Lines[N - 2] then
    Lines[N - 1] := Lines[N - 2] + (A1 - A0) * 1E-6;
end;

end.
