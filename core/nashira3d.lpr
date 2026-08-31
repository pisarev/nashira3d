{ ************************************************************************** }
{                                                                            }
{ nashira3d                                                                  }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

library nashira3d;

{$mode objfpc}{$H+}
{$PACKRECORDS C}

uses
  SysUtils, Math, GL, nsh_context, nsh_surface, nsh_render, nsh_adaptive,
  nsh_camera;

const
  NSH_OK              = 0;
  NSH_ERR_ARG         = 1;
  NSH_ERR_FORMULA     = 2;
  NSH_ERR_GPU         = 3;
  NSH_ERR_MEMORY      = 4;
  NSH_ERR_STATE       = 5;
  NSH_ERR_UNSUPPORTED = 6;
  NSH_VERSION = '0.2.0';

type
  PSession = ^TSession;
  TSession = record
    Formula   : AnsiString;
    X0, X1    : Double;
    Y0, Y1    : Double;
    Quality   : LongInt;
    Azimuth   : Double;
    Elevation : Double;
    Distance  : Double;
    Fov       : Double;
    PanX      : Double;
    PanY      : Double;
    BoxX      : Double;
    BoxY      : Double;
    BoxZ      : Double;
    Fit       : LongInt;
    Grid      : LongInt;
    Fill      : Double;
    ZFrozen   : Boolean;
    Shade     : LongInt;
    CStep     : Double;
    ZMid      : Double;
    ZSpan     : Double;
    LightAz   : Double;
    LightEl   : Double;
    Axes      : LongInt;
    CamStand  : Boolean;
    RegionView : Boolean;
    CamCx     : Double;
    CamCy     : Double;
    CamH      : Double;
    MaxExtent : Double;
    ZExag     : Double;
    RegX0, RegX1, RegY0, RegY1 : Double;
    RegOk : Boolean;
    ZK : Double;
    ZHalf0 : Double;
    ZHalf0Set : Boolean;
    DomX0, DomX1, DomY0, DomY1 : Double;
    AutoZ     : LongInt;
    AutoArmed : Boolean;
    AutoFired : LongInt;
    Obst      : array of LongInt;
    LastError : AnsiString;
    Dirty     : Boolean;
  end;

  TFnCreate     = function(out S: PSession): LongInt; cdecl;
  TFnDestroy    = procedure(S: PSession); cdecl;
  TFnSetFormula = function(S: PSession; U: PAnsiChar): LongInt; cdecl;
  TFnSetDomain  = function(S: PSession; X0, X1, Y0, Y1: Double): LongInt; cdecl;
  TFnSetQuality = function(S: PSession; Q: LongInt): LongInt; cdecl;
  TFnSetCamera  = function(S: PSession; Az, El, Dist, Fov: Double): LongInt; cdecl;
  TFnSetPan     = function(S: PSession; Dx, Dy: Double): LongInt; cdecl;
  TFnSetBox     = function(S: PSession; Sx, Sy, Sz: Double): LongInt; cdecl;
  TFnSetFit     = function(S: PSession; On_: LongInt): LongInt; cdecl;
  TFnSetGrid    = function(S: PSession; On_: LongInt): LongInt; cdecl;
  TFnSetFill    = function(S: PSession; K: Double): LongInt; cdecl;
  TFnSetLight   = function(S: PSession; Az, El: Double): LongInt; cdecl;
  TFnSetAxes    = function(S: PSession; On_: LongInt): LongInt; cdecl;
  TFnRender     = function(S: PSession; W, H: LongInt; Rgba: PByte): LongInt; cdecl;
  TFnLastError  = function(S: PSession): PAnsiChar; cdecl;
  TFnVersion    = function: PAnsiChar; cdecl;
  TFnFitZ       = function(S: PSession): LongInt; cdecl;
  TFnSetObst    = function(S: PSession; Rects: PLongInt; Count: LongInt): LongInt; cdecl;
  TFnSetCamAt   = function(S: PSession; Cx, Cy, H, Az, El, Fov: Double): LongInt; cdecl;
  TFnSetExtent  = function(S: PSession; E: Double): LongInt; cdecl;
  TFnSetZExag   = function(S: PSession; K: Double): LongInt; cdecl;
  TFnViewRegion = function(S: PSession; W, H: LongInt; Out4: PDouble): LongInt; cdecl;
  TFnSetAutoZ   = function(S: PSession; On_: LongInt): LongInt; cdecl;
  TFnAutoZFired = function(S: PSession): LongInt; cdecl;
  TFnSetShading = function(S: PSession; Mode: LongInt; Step: Double): LongInt; cdecl;
  TFnSetRegion  = function(S: PSession; Mode: LongInt): LongInt; cdecl;

  TNshApiV1 = record
    Size       : LongWord;
    Create_    : TFnCreate;
    Destroy_   : TFnDestroy;
    SetFormula : TFnSetFormula;
    SetDomain  : TFnSetDomain;
    SetQuality : TFnSetQuality;
    SetCamera  : TFnSetCamera;
    SetPan     : TFnSetPan;
    SetBox     : TFnSetBox;
    SetFit     : TFnSetFit;
    SetGrid    : TFnSetGrid;
    SetFill    : TFnSetFill;
    SetLight   : TFnSetLight;
    SetAxes    : TFnSetAxes;
    Render     : TFnRender;
    LastError  : TFnLastError;
    Version    : TFnVersion;
    FitZ       : TFnFitZ;
    SetObst    : TFnSetObst;
    SetCamAt   : TFnSetCamAt;
    SetExtent  : TFnSetExtent;
    SetZExag   : TFnSetZExag;
    ViewRegion : TFnViewRegion;
    SetAutoZ   : TFnSetAutoZ;
    AutoZFired : TFnAutoZFired;
    SetShading : TFnSetShading;
    SetRegion  : TFnSetRegion;
  end;
  PNshApiV1 = ^TNshApiV1;

var
  ApiV1 : TNshApiV1;
  LastUploader : PSession = nil;

procedure Fail(S: PSession; const Text: AnsiString);
begin
  if S <> nil then S^.LastError := Text;
end;

function DoCreate(out S: PSession): LongInt; cdecl;
begin
  S := nil;
  try
    New(S);
    FillChar(S^, SizeOf(TSession), 0);
    S^.Formula   := '';
    S^.X0 := -1;
    S^.X1 := 1;
    S^.Y0 := -1;
    S^.Y1 := 1;
    S^.DomX0 := -1;
    S^.DomX1 := 1;
    S^.DomY0 := -1;
    S^.DomY1 := 1;
    S^.Quality   := 50;
    S^.Azimuth   := 0.8;
    S^.Elevation := 0.6;
    S^.Distance  := 4;
    S^.Fov       := 0.8;
    S^.PanX      := 0;
    S^.PanY      := 0;
    S^.BoxX      := 1;
    S^.BoxY      := 1;
    S^.BoxZ      := 0.3;
    S^.Fit       := 1;
    S^.Grid      := 1;
    S^.Fill      := 2.4;
    S^.ZFrozen   := False;
    S^.ZMid      := 0;
    S^.ZSpan     := 1;
    S^.Axes      := 0;
    S^.CamStand  := False;
    S^.RegionView := False;
    S^.CamCx     := 0;
    S^.CamCy     := 0;
    S^.CamH      := 3;
    S^.MaxExtent := 0;
    S^.ZExag     := 1;
    S^.Shade     := 0;
    S^.CStep     := 0;
    S^.AutoZ     := 0;
    S^.AutoArmed := True;
    S^.AutoFired := 0;
    S^.ZK        := 1;
    S^.ZHalf0    := 1;
    S^.ZHalf0Set := False;
    S^.RegOk     := False;
    S^.LastError := '';
    S^.Dirty     := True;
    Result := NSH_OK;
  except
    if S <> nil then
    begin
      Dispose(S);
      S := nil;
    end;
    Result := NSH_ERR_MEMORY;
  end;
end;

procedure DoDestroy(S: PSession); cdecl;
begin
  try
    if S <> nil then
    begin
      if LastUploader = S then LastUploader := nil;
      S^.Formula := '';
      S^.LastError := '';
      Dispose(S);
    end;
  except
  end;
end;

function DoSetFormula(S: PSession; U: PAnsiChar): LongInt; cdecl;
var
  Err: AnsiString;
begin
  try
    if (S = nil) or (U = nil) then Exit(NSH_ERR_ARG);
    if not FormulaOk(AnsiString(U), Err) then
    begin
      Fail(S, Err);
      Exit(NSH_ERR_FORMULA);
    end;
    if S^.Formula <> AnsiString(U) then
    begin
      S^.Formula := AnsiString(U);
      S^.Dirty := True;
      S^.ZFrozen := False;
      S^.ZHalf0Set := False;
    end;
    Result := NSH_OK;
  except
    on E: Exception do
    begin
      Fail(S, AnsiString(E.Message));
      Result := NSH_ERR_FORMULA;
    end;
  end;
end;

function DoSetDomain(S: PSession; X0, X1, Y0, Y1: Double): LongInt; cdecl;
begin
  try
    if S = nil then Exit(NSH_ERR_ARG);
    if (X1 <= X0) or (Y1 <= Y0) then
    begin
      Fail(S, 'domain must satisfy x0 < x1 and y0 < y1');
      Exit(NSH_ERR_ARG);
    end;
    S^.X0 := X0;
    S^.X1 := X1;
    S^.Y0 := Y0;
    S^.Y1 := Y1;
    S^.DomX0 := X0;
    S^.DomX1 := X1;
    S^.DomY0 := Y0;
    S^.DomY1 := Y1;
    S^.Dirty := True;
    Result := NSH_OK;
  except
    Result := NSH_ERR_ARG;
  end;
end;

function DoSetQuality(S: PSession; Q: LongInt): LongInt; cdecl;
begin
  try
    if S = nil then Exit(NSH_ERR_ARG);
    if (Q < 0) or (Q > 100) then
    begin
      Fail(S, 'quality must be in 0..100');
      Exit(NSH_ERR_ARG);
    end;
    S^.Quality := Q;
    S^.Dirty := True;
    Result := NSH_OK;
  except
    Result := NSH_ERR_ARG;
  end;
end;

function DoSetCamera(S: PSession; Az, El, Dist, Fov: Double): LongInt; cdecl;
begin
  try
    if S = nil then Exit(NSH_ERR_ARG);
    if Dist <= 0 then
    begin
      Fail(S, 'camera distance must be positive');
      Exit(NSH_ERR_ARG);
    end;
    S^.Azimuth := Az;
    S^.Elevation := El;
    S^.Distance := Dist;
    S^.Fov := Fov;
    if S^.CamStand then
    begin
      S^.CamStand := False;
      S^.RegOk := False;
      S^.Dirty := True;
    end;
    Result := NSH_OK;
  except
    Result := NSH_ERR_ARG;
  end;
end;

function DoSetPan(S: PSession; Dx, Dy: Double): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if IsNan(Dx) or IsNan(Dy) or IsInfinite(Dx) or IsInfinite(Dy) then
  begin
    Fail(S, 'pan must be a finite number');
    Exit(NSH_ERR_ARG);
  end;
  S^.PanX := Dx;
  S^.PanY := Dy;
  Result := NSH_OK;
end;

function DoSetBox(S: PSession; Sx, Sy, Sz: Double): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if IsNan(Sx) or IsNan(Sy) or IsNan(Sz) or IsInfinite(Sx) or IsInfinite(Sy) or IsInfinite(Sz) then
  begin
    Fail(S, 'box proportions must be finite numbers');
    Exit(NSH_ERR_ARG);
  end;
  if (Sx <= 0) or (Sy <= 0) or (Sz <= 0) then
  begin
    Fail(S, 'box proportions must be positive');
    Exit(NSH_ERR_ARG);
  end;
  S^.BoxX := Sx;
  S^.BoxY := Sy;
  S^.BoxZ := Sz;
  Result := NSH_OK;
end;

function DoSetFit(S: PSession; On_: LongInt): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if On_ <> 0 then
    S^.Fit := 1
  else
    S^.Fit := 0;
  Result := NSH_OK;
end;

function DoSetGrid(S: PSession; On_: LongInt): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if On_ <> 0 then
    S^.Grid := 1
  else
    S^.Grid := 0;
  Result := NSH_OK;
end;

function DoSetFill(S: PSession; K: Double): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if IsNan(K) or IsInfinite(K) or (K <= 0) then
  begin
    Fail(S, 'fill must be a positive finite number');
    Exit(NSH_ERR_ARG);
  end;
  S^.Fill := K;
  Result := NSH_OK;
end;

procedure SceneSlab(S: PSession; out Z0, Zmin, Zmax: Double);
var
  K: Double;
begin
  K := S^.ZK * S^.ZExag;
  Z0 := K * S^.ZMid;
  Zmin := K * (S^.ZMid - S^.ZSpan / 2);
  Zmax := K * (S^.ZMid + S^.ZSpan / 2);
end;

function SessionCam(S: PSession): TCam;
begin
  Result.Cx := S^.CamCx;
  Result.Cy := S^.CamCy;
  Result.H := S^.CamH;
  Result.Az := S^.Azimuth;
  Result.El := S^.Elevation;
  Result.Fov := S^.Fov;
end;

function DoSetCameraAt(S: PSession; Cx, Cy, H, Az, El, Fov: Double): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if IsNan(Cx) or IsNan(Cy) or IsNan(H) or IsNan(Az) or IsNan(El) or IsNan(Fov) or
    IsInfinite(Cx) or IsInfinite(Cy) or IsInfinite(H) or
    IsInfinite(Az) or IsInfinite(El) or IsInfinite(Fov) then
    begin
      Fail(S, 'camera numbers must be finite'); Exit(NSH_ERR_ARG);
    end;
  if (Fov <= 0) or (Fov >= Pi) then
  begin
    Fail(S, 'field of view must be between 0 and pi'); Exit(NSH_ERR_ARG);
  end;
  S^.CamCx := Cx;
  S^.CamCy := Cy;
  S^.CamH := H;
  S^.Azimuth := Az;
  S^.Elevation := El;
  S^.Fov := Fov;
  S^.CamStand := True;
  Result := NSH_OK;
end;

function DoSetMaxExtent(S: PSession; E: Double): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if IsNan(E) or IsInfinite(E) or (E < 0) then
  begin
    Fail(S, 'max ground extent must be a finite number, zero for default');
        Exit(NSH_ERR_ARG);
      end;
  S^.MaxExtent := E;
  Result := NSH_OK;
end;

function DoSetZExag(S: PSession; K: Double): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if IsNan(K) or IsInfinite(K) or (K <= 0) then
  begin
    Fail(S, 'vertical exaggeration must be a positive finite number');
        Exit(NSH_ERR_ARG);
      end;
  S^.ZExag := K;
  Result := NSH_OK;
end;

function DoViewRegion(S: PSession; W, H: LongInt; Out4: PDouble): LongInt; cdecl;
var
  Rg: TRegion;
  Z0, Zmin, Zmax: Double;
  P: PDouble;
begin
  if (S = nil) or (Out4 = nil) then Exit(NSH_ERR_ARG);
  if (W <= 0) or (H <= 0) then
  begin
    Fail(S, 'width and height must be positive'); Exit(NSH_ERR_ARG);
  end;
  if not S^.CamStand then
  begin
    Fail(S, 'view region is defined only for a standing-point camera');
        Exit(NSH_ERR_STATE);
      end;
  SceneSlab(S, Z0, Zmin, Zmax);
  Rg := CamRegion(SessionCam(S), W / H, Z0, Zmin, Zmax, S^.MaxExtent);
  if not Rg.Ok then
  begin
    Fail(S, 'nothing of the surface is in view'); Exit(NSH_ERR_STATE);
  end;
  P := Out4;
  P^ := Rg.X0;
  Inc(P);
  P^ := Rg.X1;
  Inc(P);
  P^ := Rg.Y0;
  Inc(P);
  P^ := Rg.Y1;
  Result := NSH_OK;
end;

function DoSetAutoZ(S: PSession; On_: LongInt): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  S^.AutoZ := Ord(On_ <> 0);
  if S^.AutoZ <> 0 then
  begin
    S^.AutoArmed := True;
    S^.Dirty := True;
  end;
  Result := NSH_OK;
end;

function DoSetShading(S: PSession; Mode: LongInt; Step: Double): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if (Mode < 0) or (Mode > 2) then
  begin
    Fail(S, 'shading must be 0 (contours), 1 (color) or 2 (both)');
        Exit(NSH_ERR_ARG);
      end;
  if IsNan(Step) or IsInfinite(Step) or (Step < 0) then
  begin
    Fail(S, 'contour step must be a finite non-negative number');
        Exit(NSH_ERR_ARG);
      end;
  S^.Shade := Mode;
  S^.CStep := Step;
  Result := NSH_OK;
end;

function DoSetRegion(S: PSession; Mode: LongInt): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if (Mode < 0) or (Mode > 1) then
  begin
    Fail(S, 'region mode must be 0 (declared) or 1 (from the view)');
        Exit(NSH_ERR_ARG);
      end;
  if S^.RegionView <> (Mode <> 0) then
  begin
    S^.RegionView := Mode <> 0;
    S^.RegOk := False;
    S^.Dirty := True;
  end;
  Result := NSH_OK;
end;

function DoAutoZFired(S: PSession): LongInt; cdecl;
begin
  if S = nil then Exit(0);
  Result := S^.AutoFired;
  S^.AutoFired := 0;
end;

function DoSetObstacles(S: PSession; Rects: PLongInt; Count: LongInt): LongInt; cdecl;
var
  I: LongInt;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  if Count < 0 then
  begin
    Fail(S, 'obstacle count must not be negative'); Exit(NSH_ERR_ARG);
  end;
  if (Count > 0) and (Rects = nil) then
  begin
    Fail(S, 'obstacle list is null but the count is not zero'); Exit(NSH_ERR_ARG);
  end;
  if (Count mod 4) <> 0 then
  begin
    Fail(S, 'obstacle count must be a multiple of four'); Exit(NSH_ERR_ARG);
  end;
  if Count > 256 then
  begin
    Fail(S, 'at most 64 obstacles'); Exit(NSH_ERR_ARG);
  end;
  SetLength(S^.Obst, Count);
  for I := 0 to Count - 1 do S^.Obst[I] := PLongInt(PByte(Rects) + I * SizeOf(LongInt))^;
  Result := NSH_OK;
end;

function DoFitZ(S: PSession): LongInt; cdecl;
begin
  if S = nil then Exit(NSH_ERR_ARG);
  S^.ZFrozen := False;
  S^.Dirty := True;
  Result := NSH_OK;
end;

function DoSetLight(S: PSession; Az, El: Double): LongInt; cdecl;
begin
  try
    if S = nil then Exit(NSH_ERR_ARG);
    S^.LightAz := Az;
    S^.LightEl := El;
    Result := NSH_OK;
  except
    Result := NSH_ERR_ARG;
  end;
end;

function DoSetAxes(S: PSession; On_: LongInt): LongInt; cdecl;
begin
  try
    if S = nil then Exit(NSH_ERR_ARG);
    if On_ <> 0 then
      S^.Axes := 1
    else
      S^.Axes := 0;
    Result := NSH_OK;
  except
    Result := NSH_ERR_ARG;
  end;
end;

procedure FlipRows(Rgba: PByte; W, H: LongInt);
var
  Row  : array of Byte;
  Y, N : LongInt;
  A, B : PByte;
begin
  N := W * 4;
  SetLength(Row, N);
  for Y := 0 to (H div 2) - 1 do
  begin
    A := Rgba + Y * N;
    B := Rgba + (H - 1 - Y) * N;
    Move(A^, Row[0], N);
    Move(B^, A^, N);
    Move(Row[0], B^, N);
  end;
end;

function DoRender(S: PSession; W, H: LongInt; Rgba: PByte): LongInt; cdecl;
var
  Mesh : TSurface;
  Err  : AnsiString;
  Lx, Ly : TDoubleArray;
  DCam : TDrawCam;
  Rg : TRegion;
  Cam : TCam;
  Dir : TVec3;
  SlabZ0, SlabMin, SlabMax, Half, BX, BY, BZ : Double;
  AutoNeed, AutoRatio : Double;
  DoFit, FrozeNow, Again : Boolean;
  SideN : LongInt;
  Pass : LongInt;
begin
  try
    if (S = nil) or (Rgba = nil) then Exit(NSH_ERR_ARG);
    if (W <= 0) or (H <= 0) then
    begin
      Fail(S, 'width and height must be positive');
      Exit(NSH_ERR_ARG);
    end;
    if not CtxCreate then
    begin
      Fail(S, CtxError);
      Exit(NSH_ERR_GPU);
    end;
    if not CtxTarget(W, H) then
    begin
      Fail(S, CtxError);
      Exit(NSH_ERR_GPU);
    end;
    if not RndInit(Err) then
    begin
      Fail(S, Err); Exit(NSH_ERR_GPU);
    end;
    if S^.RegionView and (not S^.CamStand) then
    begin
      Fail(S, 'region from view needs a standing camera: call set_camera_at');
      Exit(NSH_ERR_STATE);
    end;
    Pass := 0;
    repeat
    Inc(Pass);
    Again := False;
    FrozeNow := False;
    if not S^.RegionView then
    begin
      if (S^.X0 <> S^.DomX0) or (S^.X1 <> S^.DomX1) or
        (S^.Y0 <> S^.DomY0) or (S^.Y1 <> S^.DomY1) then
        begin
          S^.X0 := S^.DomX0;
          S^.X1 := S^.DomX1;
          S^.Y0 := S^.DomY0;
          S^.Y1 := S^.DomY1;
          S^.Dirty := True;
        end;
      S^.RegOk := False;
    end;
    if S^.RegionView and S^.ZFrozen then
    begin
      SceneSlab(S, SlabZ0, SlabMin, SlabMax);
      Rg := CamRegion(SessionCam(S), W / H, SlabZ0, SlabMin, SlabMax, S^.MaxExtent);
      if Rg.Ok then
      begin
        S^.RegX0 := Rg.X0;
        S^.RegX1 := Rg.X1;
        S^.RegY0 := Rg.Y0;
        S^.RegY1 := Rg.Y1;
        S^.RegOk := True;
        if (S^.X0 <> Rg.X0) or (S^.X1 <> Rg.X1) or (S^.Y0 <> Rg.Y0) or (S^.Y1 <> Rg.Y1) then
        begin
          S^.X0 := Rg.X0;
          S^.X1 := Rg.X1;
          S^.Y0 := Rg.Y0;
          S^.Y1 := Rg.Y1;
          S^.Dirty := True;
        end;
      end
      else
        S^.RegOk := False;
    end;
    if S^.Dirty or (S <> LastUploader) then
    begin
      if S^.Formula = '' then
      begin
        Fail(S, 'no formula: call set_formula first');
        Exit(NSH_ERR_STATE);
      end;
      if GetEnvironmentVariable('NASHIRA3D_ADAPTIVE') = '1' then
      begin
        if not ChooseSamples(S^.Formula, S^.X0, S^.X1, S^.Y0, S^.Y1,
                             SideFromQuality(S^.Quality), Lx, Ly, Err) then
          begin
            Fail(S, Err); Exit(NSH_ERR_FORMULA);
          end;
        if not BuildSurfaceFrom(S^.Formula, Lx, Ly, Mesh, Err) then
        begin
          Fail(S, Err); Exit(NSH_ERR_FORMULA);
        end;
      end
      else
      if S^.RegionView then
      begin
        SideN := SideFromQuality(S^.Quality);
        SceneSlab(S, SlabZ0, SlabMin, SlabMax);
        CamAxisLines(SessionCam(S), S^.X0, S^.X1, (S^.Y0 + S^.Y1) / 2, SlabZ0, True, SideN, Lx);
        CamAxisLines(SessionCam(S), S^.Y0, S^.Y1, (S^.X0 + S^.X1) / 2, SlabZ0, False, SideN, Ly);
        if not BuildSurfaceFrom(S^.Formula, Lx, Ly, Mesh, Err) then
        begin
          Fail(S, Err); Exit(NSH_ERR_FORMULA);
        end;
      end
      else
      if not BuildSurface(S^.Formula, S^.X0, S^.X1, S^.Y0, S^.Y1, S^.Quality, Mesh, Err) then
      begin
        Fail(S, Err); Exit(NSH_ERR_FORMULA);
      end;
      if not S^.ZFrozen then
      begin
        S^.ZMid := (Mesh.ZMin + Mesh.ZMax) / 2;
        S^.ZSpan := Mesh.ZMax - Mesh.ZMin;
        if S^.ZSpan < 1E-12 then S^.ZSpan := 1;
        if not S^.ZHalf0Set then
        begin
          S^.ZHalf0 := Max((S^.DomX1 - S^.DomX0) / 2, (S^.DomY1 - S^.DomY0) / 2);
          if (S^.ZHalf0 <= 0) or IsNan(S^.ZHalf0) or IsInfinite(S^.ZHalf0) then
            S^.ZHalf0 := 1;
          S^.ZHalf0Set := True;
        end;
        S^.ZK := 0.6 * S^.ZHalf0 / S^.ZSpan;
        if (S^.ZK <= 0) or IsNan(S^.ZK) or IsInfinite(S^.ZK) then S^.ZK := 1;
        S^.ZFrozen := True;
        FrozeNow := True;
      end;
      if (S^.AutoZ <> 0) and S^.ZFrozen and (S^.ZSpan > 0) then
      begin
        AutoNeed := Mesh.ZMax - Mesh.ZMin;
        if AutoNeed > 0 then
        begin
          AutoRatio := AutoNeed / S^.ZSpan;
          if S^.AutoArmed and (AutoRatio > 2.0) then
          begin
            S^.ZMid := (Mesh.ZMin + Mesh.ZMax) / 2;
            S^.ZSpan := AutoNeed;
            S^.ZK := 0.6 * S^.ZHalf0 / S^.ZSpan;
            if (S^.ZK <= 0) or IsNan(S^.ZK) or IsInfinite(S^.ZK) then S^.ZK := 1;
            S^.AutoArmed := False;
            S^.AutoFired := 1;
            AutoRatio := 1;
          end;
          if (not S^.AutoArmed) and (AutoRatio < 1.5) then
            S^.AutoArmed := True;
        end;
      end;
      if not RndUpload(Mesh, S^.ZMid, S^.ZSpan, Err) then
      begin
        Fail(S, Err); Exit(NSH_ERR_GPU);
      end;
      S^.Dirty := False;
      LastUploader := S;
      if FrozeNow and S^.RegionView then Again := True;
    end;
    until (not Again) or (Pass >= 2);
    RndObstacles(S^.Obst);
    RndShading(S^.Shade, S^.CStep);
    RndDissolve(S^.RegionView);
    DCam.Fov := S^.Fov;
    BX := S^.BoxX;
    BY := S^.BoxY;
    BZ := S^.BoxZ;
    DoFit := S^.Fit <> 0;
    if S^.CamStand then
    begin
      Half := Max((S^.X1 - S^.X0) / 2, (S^.Y1 - S^.Y0) / 2);
      if Half < 1E-300 then Half := 1;
      SceneSlab(S, SlabZ0, SlabMin, SlabMax);
      Cam := SessionCam(S);
      BX := 1;
      BY := 1;
      BZ := (S^.ZK * S^.ZExag) * S^.ZSpan / (2 * Half);
      if (BZ <= 0) or IsNan(BZ) or IsInfinite(BZ) then BZ := 0.3;
      DCam.UseEye := True;
      DCam.Ex := (S^.CamCx - (S^.X0 + S^.X1) / 2) / Half;
      DCam.Ey := (S^.CamCy - (S^.Y0 + S^.Y1) / 2) / Half;
      DCam.Ez := S^.CamH / Half;
      Dir := CamForward(Cam);
      DCam.Dx := Dir.X;
      DCam.Dy := Dir.Y;
      DCam.Dz := Dir.Z;
      DoFit := False;
    end
    else begin
      DCam.UseEye := False;
      DCam.Az := S^.Azimuth;
      DCam.El := S^.Elevation;
      DCam.Dist := S^.Distance;
    end;
    if not RndDraw(W, H, DCam,
                   S^.PanX, S^.PanY, BX, BY, BZ, S^.Fill,
                   S^.LightAz, S^.LightEl, DoFit, S^.Grid <> 0,
                   S^.Axes <> 0, Err) then
      begin
        Fail(S, Err); Exit(NSH_ERR_GPU);
      end;
    if not CtxResolve then
    begin
      Fail(S, CtxError); Exit(NSH_ERR_GPU);
    end;
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, Rgba);
    FlipRows(Rgba, W, H);
    Result := NSH_OK;
  except
    Result := NSH_ERR_GPU;
  end;
end;

function DoLastError(S: PSession): PAnsiChar; cdecl;
begin
  if S = nil then Exit(nil);
  Result := PAnsiChar(S^.LastError);
end;

function DoVersion: PAnsiChar; cdecl;
begin
  Result := PAnsiChar(NSH_VERSION);
end;

function nsh_get_api(Version: LongWord): PNshApiV1; cdecl;
begin
  if Version <> 1 then Exit(nil);
  Result := @ApiV1;
end;

exports
  nsh_get_api;

begin
  FillChar(ApiV1, SizeOf(ApiV1), 0);
  ApiV1.Size       := SizeOf(TNshApiV1);
  ApiV1.Create_    := @DoCreate;
  ApiV1.Destroy_   := @DoDestroy;
  ApiV1.SetFormula := @DoSetFormula;
  ApiV1.SetDomain  := @DoSetDomain;
  ApiV1.SetQuality := @DoSetQuality;
  ApiV1.SetCamera  := @DoSetCamera;
  ApiV1.SetPan     := @DoSetPan;
  ApiV1.SetBox     := @DoSetBox;
  ApiV1.SetFit     := @DoSetFit;
  ApiV1.SetGrid    := @DoSetGrid;
  ApiV1.SetFill    := @DoSetFill;
  ApiV1.SetLight   := @DoSetLight;
  ApiV1.SetAxes    := @DoSetAxes;
  ApiV1.Render     := @DoRender;
  ApiV1.LastError  := @DoLastError;
  ApiV1.Version    := @DoVersion;
  ApiV1.FitZ       := @DoFitZ;
  ApiV1.SetObst    := @DoSetObstacles;
  ApiV1.SetCamAt   := @DoSetCameraAt;
  ApiV1.SetExtent  := @DoSetMaxExtent;
  ApiV1.SetZExag   := @DoSetZExag;
  ApiV1.ViewRegion := @DoViewRegion;
  ApiV1.SetAutoZ   := @DoSetAutoZ;
  ApiV1.AutoZFired := @DoAutoZFired;
  ApiV1.SetShading := @DoSetShading;
  ApiV1.SetRegion  := @DoSetRegion;
end.
