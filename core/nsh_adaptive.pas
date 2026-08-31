{ ************************************************************************** }
{                                                                            }
{ nsh_adaptive                                                               }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

unit nsh_adaptive;

{$mode objfpc}{$H+}

interface

type
  TDoubleArray = array of Double;

function ChooseSamples(const Formula: AnsiString; X0, X1, Y0, Y1: Double; Budget: LongInt;
  out Xs, Ys: TDoubleArray; out Error: AnsiString): Boolean;

implementation

uses
  SysUtils, Math, nsh_surface;

const
  START_LINES = 17;
  MAX_STEPS   = 400;
  BATCH_DIV   = 8;

procedure Uniform(out A: TDoubleArray; Lo, Hi: Double; N: LongInt);
var
  I: LongInt;
begin
  SetLength(A, N);
  for I := 0 to N - 1 do A[I] := Lo + (Hi - Lo) * I / (N - 1);
end;

procedure ScoreGaps(const Z: array of Double; NX, NY: LongInt; const A: TDoubleArray;
  AlongX: Boolean; out Score: TDoubleArray);
var
  I, J, K, N: LongInt;
  Curv: TDoubleArray;
  C, V: Double;
begin
  if AlongX then
    N := NX
  else
    N := NY;
  SetLength(Curv, N);
  for I := 0 to N - 1 do Curv[I] := 0;
  for I := 1 to N - 2 do
  begin
    C := 0;
    if AlongX then
      for J := 0 to NY - 1 do
      begin
        V := Z[J * NX + I - 1] - 2 * Z[J * NX + I] + Z[J * NX + I + 1];
        if not (IsNan(V) or IsInfinite(V)) then C := C + Abs(V);
      end
    else
      for J := 0 to NX - 1 do
      begin
        V := Z[(I - 1) * NX + J] - 2 * Z[I * NX + J] + Z[(I + 1) * NX + J];
        if not (IsNan(V) or IsInfinite(V)) then C := C + Abs(V);
      end;
    Curv[I] := C;
  end;
  SetLength(Score, N - 1);
  for K := 0 to N - 2 do
    Score[K] := (Curv[K] + Curv[K + 1]) * (A[K + 1] - A[K]);
end;

function SplitTopK(var A: TDoubleArray; const Score: TDoubleArray; K: LongInt): LongInt;
var
  Idx  : array of LongInt;
  Mids : TDoubleArray;
  I, J, N, Take : LongInt;
  T : LongInt;
  Merged : TDoubleArray;
  P, Q : LongInt;
begin
  Result := 0;
  N := Length(Score);
  if (N < 1) or (K < 1) then Exit;
  SetLength(Idx, N);
  for I := 0 to N - 1 do Idx[I] := I;
  Take := 0;
  for I := 0 to N - 1 do
  begin
    if Take >= K then Break;
    for J := I + 1 to N - 1 do
      if Score[Idx[J]] > Score[Idx[I]] then
      begin
        T := Idx[I];
        Idx[I] := Idx[J];
        Idx[J] := T;
      end;
    if Score[Idx[I]] <= 0 then Break;
    Inc(Take);
  end;
  if Take = 0 then Exit;
  SetLength(Mids, 0);
  for I := 0 to Take - 1 do
  begin
    J := Idx[I];
    if (A[J + 1] - A[J]) > 1E-12 then
    begin
      SetLength(Mids, Length(Mids) + 1);
      Mids[High(Mids)] := (A[J] + A[J + 1]) / 2;
    end;
  end;
  if Length(Mids) = 0 then Exit;
  for I := 0 to High(Mids) - 1 do
    for J := 0 to High(Mids) - 1 - I do
      if Mids[J] > Mids[J + 1] then
      begin
        A[0] := A[0];
        T := 0;
        Mids[J] := Mids[J] + Mids[J + 1];
        Mids[J + 1] := Mids[J] - Mids[J + 1];
        Mids[J] := Mids[J] - Mids[J + 1];
      end;
  SetLength(Merged, Length(A) + Length(Mids));
  P := 0;
  Q := 0;
  for I := 0 to High(Merged) do
  begin
    if (P <= High(A)) and ((Q > High(Mids)) or (A[P] <= Mids[Q])) then
    begin
      Merged[I] := A[P];
      Inc(P);
    end
    else begin
      Merged[I] := Mids[Q];
      Inc(Q);
    end;
  end;
  A := Merged;
  Result := Length(Mids);
end;

function ChooseSamples(const Formula: AnsiString; X0, X1, Y0, Y1: Double; Budget: LongInt;
  out Xs, Ys: TDoubleArray; out Error: AnsiString): Boolean;
var
  Z          : array of Double;
  ScoreX     : TDoubleArray;
  ScoreY     : TDoubleArray;
  Pass, K    : LongInt;
  Grew       : Boolean;
begin
  Result := False;
  Error := '';
  if Budget < START_LINES then Budget := START_LINES;
  Uniform(Xs, X0, X1, START_LINES);
  Uniform(Ys, Y0, Y1, START_LINES);
  Pass := 0;
  while (Length(Xs) < Budget) or (Length(Ys) < Budget) do
  begin
    Inc(Pass);
    if Pass > MAX_STEPS then Break;
    SetLength(Z, Length(Xs) * Length(Ys));
    if not EvalGrid(Formula, Xs, Ys, Z, Error) then Exit;
    Grew := False;
    if Length(Xs) < Budget then
    begin
      K := (Budget - Length(Xs) + BATCH_DIV - 1) div BATCH_DIV;
      ScoreGaps(Z, Length(Xs), Length(Ys), Xs, True, ScoreX);
      if SplitTopK(Xs, ScoreX, K) > 0 then Grew := True;
      SetLength(Z, Length(Xs) * Length(Ys));
      if not EvalGrid(Formula, Xs, Ys, Z, Error) then Exit;
    end;
    if Length(Ys) < Budget then
    begin
      K := (Budget - Length(Ys) + BATCH_DIV - 1) div BATCH_DIV;
      ScoreGaps(Z, Length(Xs), Length(Ys), Ys, False, ScoreY);
      if SplitTopK(Ys, ScoreY, K) > 0 then Grew := True;
    end;
    if not Grew then Break;
  end;
  Result := True;
end;

end.
