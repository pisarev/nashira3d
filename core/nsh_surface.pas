{ ************************************************************************** }
{                                                                            }
{ nsh_surface                                                                }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

unit nsh_surface;

{$mode objfpc}{$H+}

interface

type
  TVertex = packed record
    X, Y, Z    : Single;
    NX, NY, NZ : Single;
  end;

  TSurface = record
    Verts      : array of TVertex;
    Idx        : array of LongWord;
    Side       : LongInt;
    ZMin, ZMax : Double;
    Holes      : LongInt;
  end;

function SideFromQuality(Q: LongInt): LongInt;

procedure EngineStats(out Compiles, Hits, Misses: Int64);

function EvalGrid(const Formula: AnsiString; const Xs, Ys: array of Double; var Z: array of Double;
  out Error: AnsiString): Boolean;

function FormulaOk(const Formula: AnsiString; out Error: AnsiString): Boolean;

function BuildSurface(const Formula: AnsiString; X0, X1, Y0, Y1: Double; Quality: LongInt;
  out S: TSurface; out Error: AnsiString): Boolean;

function BuildSurfaceFrom(const Formula: AnsiString; const Xs, Ys: array of Double; out S: TSurface;
  out Error: AnsiString): Boolean;

implementation

uses
  SysUtils, Math, Parser, ParseJit.Parser;

var
  GParser : TJitParser = nil;
  GVarX   : Double = 0;
  GVarY   : Double = 0;

procedure EngineStats(out Compiles, Hits, Misses: Int64);
begin
  if GParser = nil then
  begin
    Compiles := 0;
    Hits := 0;
    Misses := 0;
  end
  else begin
    Compiles := GParser.CompileCount;
    Hits := GParser.HitCount;
    Misses := GParser.MissCount;
  end;
end;

function Engine: TJitParser;
begin
  if GParser = nil then
  begin
    GParser := TJitParser.Create(nil);
    GParser.AddVariable('x', GVarX);
    GParser.AddVariable('y', GVarY);
  end;
  Result := GParser;
end;

function FormulaOk(const Formula: AnsiString; out Error: AnsiString): Boolean;
var
  In1    : array[0..0] of Double;
  Out1   : array[0..0] of Double;
begin
  Error := '';
  Result := False;
  if Trim(Formula) = '' then
  begin
    Error := 'formula is empty';
    Exit;
  end;
  begin
    try
      GVarY := 1;
      In1[0] := 1;
      Result := Engine.ExecuteMany(string(Formula), GVarX, In1, Out1);
      if not Result then Error := 'the formula did not parse';
    except
      on E: Exception do
      begin
        Error := AnsiString(E.Message);
        Result := False;
      end;
    end;
  end;
end;

function EvalGrid(const Formula: AnsiString; const Xs, Ys: array of Double; var Z: array of Double;
  out Error: AnsiString): Boolean;
var
  Row  : array of Double;
  I, J : LongInt;
  NX   : LongInt;
begin
  Error := '';
  Result := False;
  NX := Length(Xs);
  if (NX < 2) or (Length(Ys) < 2) then
  begin
    Error := 'too few sample lines';
    Exit;
  end;
  if Length(Z) < NX * Length(Ys) then
  begin
    Error := 'output grid is too small';
    Exit;
  end;
  SetLength(Row, NX);
  try
    for J := 0 to High(Ys) do
    begin
      GVarY := Ys[J];
      if not Engine.ExecuteMany(string(Formula), GVarX, Xs, Row) then
      begin
        Error := 'formula did not compile or evaluate';
        Exit;
      end;
      for I := 0 to NX - 1 do Z[J * NX + I] := Row[I];
    end;
  except
    on E: Exception do
    begin
      Error := AnsiString(E.Message);
      Exit;
    end;
  end;
  Result := True;
end;

function SideFromQuality(Q: LongInt): LongInt;
begin
  if Q < 0 then Q := 0;
  if Q > 100 then Q := 100;
  Result := 16 + Round(Q * 2.4);
end;

function Finite(const V: Double): Boolean; inline;
begin
  Result := (not IsNan(V)) and (not IsInfinite(V));
end;

function BuildSurfaceFrom(const Formula: AnsiString; const Xs, Ys: array of Double; out S: TSurface;
  out Error: AnsiString): Boolean;
var
  NX, NY, I, J, K, Base : LongInt;
  Z : array of Double;
  Zc, Zl, Zr, Zd, Zu : Double;
  Sx, Sy, Sz, Len, Hx, Hy : Double;
  A, B, C, D : LongInt;
begin
  Result := False;
  Error := '';
  S.Side := 0;
  S.Holes := 0;
  S.ZMin := 0;
  S.ZMax := 0;
  S.Verts := nil;
  S.Idx := nil;
  NX := Length(Xs);
  NY := Length(Ys);
  if (NX < 2) or (NY < 2) then
  begin
    Error := 'too few sample lines';
    Exit;
  end;
  SetLength(Z, NX * NY);
  if not EvalGrid(Formula, Xs, Ys, Z, Error) then Exit;
  S.ZMin := MaxDouble;
  S.ZMax := -MaxDouble;
  for K := 0 to NX * NY - 1 do
    if Finite(Z[K]) then
    begin
      if Z[K] < S.ZMin then S.ZMin := Z[K];
      if Z[K] > S.ZMax then S.ZMax := Z[K];
    end;
  if S.ZMin > S.ZMax then
  begin
    Error := 'the formula gave no finite value anywhere in the domain';
    Exit;
  end;
  if S.ZMax - S.ZMin < 1E-12 then S.ZMax := S.ZMin + 1E-12;
  SetLength(S.Verts, NX * NY);
  for J := 0 to NY - 1 do
    for I := 0 to NX - 1 do
    begin
      K := J * NX + I;
      S.Verts[K].X := Xs[I];
      S.Verts[K].Y := Ys[J];
      if Finite(Z[K]) then
        S.Verts[K].Z := Z[K]
      else
        S.Verts[K].Z := 0;
      Zc := Z[K];
      if not Finite(Zc) then Zc := 0;
      if I > 0      then
        Zl := Z[K - 1]
      else
        Zl := Zc;
      if I < NX - 1 then
        Zr := Z[K + 1]
      else
        Zr := Zc;
      if J > 0      then
        Zd := Z[K - NX]
      else
        Zd := Zc;
      if J < NY - 1 then
        Zu := Z[K + NX]
      else
        Zu := Zc;
      if not Finite(Zl) then Zl := Zc;
      if not Finite(Zr) then Zr := Zc;
      if not Finite(Zd) then Zd := Zc;
      if not Finite(Zu) then Zu := Zc;
      if I = 0 then
        Hx := Xs[1] - Xs[0]
      else if I = NX - 1 then
        Hx := Xs[NX - 1] - Xs[NX - 2]
      else
        Hx := Xs[I + 1] - Xs[I - 1];
      if J = 0 then
        Hy := Ys[1] - Ys[0]
      else if J = NY - 1 then
        Hy := Ys[NY - 1] - Ys[NY - 2]
      else
        Hy := Ys[J + 1] - Ys[J - 1];
      if Abs(Hx) < 1E-15 then Hx := 1;
      if Abs(Hy) < 1E-15 then Hy := 1;
      Sx := -(Zr - Zl) / Hx;
      Sy := -(Zu - Zd) / Hy;
      Sz := 1;
      Len := Sqrt(Sx * Sx + Sy * Sy + Sz * Sz);
      if Len < 1E-12 then Len := 1;
      S.Verts[K].NX := Sx / Len;
      S.Verts[K].NY := Sy / Len;
      S.Verts[K].NZ := Sz / Len;
    end;
  SetLength(S.Idx, (NX - 1) * (NY - 1) * 6);
  Base := 0;
  for J := 0 to NY - 2 do
    for I := 0 to NX - 2 do
    begin
      A := J * NX + I;
      B := A + 1;
      C := A + NX;
      D := C + 1;
      if not (Finite(Z[A]) and Finite(Z[B]) and Finite(Z[C]) and Finite(Z[D])) then
      begin
        Inc(S.Holes);
        Continue;
      end;
      S.Idx[Base + 0] := A;
      S.Idx[Base + 1] := C;
      S.Idx[Base + 2] := B;
      S.Idx[Base + 3] := B;
      S.Idx[Base + 4] := C;
      S.Idx[Base + 5] := D;
      Inc(Base, 6);
    end;
  SetLength(S.Idx, Base);
  S.Side := NX;
  Result := True;
end;

function BuildSurface(const Formula: AnsiString; X0, X1, Y0, Y1: Double; Quality: LongInt;
  out S: TSurface; out Error: AnsiString): Boolean;
var
  N, I : LongInt;
  Xs, Ys : array of Double;
begin
  Result := False;
  Error := '';
  if Trim(Formula) = '' then
  begin
    Error := 'formula is empty';
    Exit;
  end;
  if (X1 <= X0) or (Y1 <= Y0) then
  begin
    Error := 'empty domain';
    Exit;
  end;
  N := SideFromQuality(Quality);
  SetLength(Xs, N);
  SetLength(Ys, N);
  for I := 0 to N - 1 do
  begin
    Xs[I] := X0 + (X1 - X0) * I / (N - 1);
    Ys[I] := Y0 + (Y1 - Y0) * I / (N - 1);
  end;
  Result := BuildSurfaceFrom(Formula, Xs, Ys, S, Error);
end;

finalization
  if GParser <> nil then
  begin
    GParser.Free;
    GParser := nil;
  end;

end.
