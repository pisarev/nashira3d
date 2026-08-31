{ ************************************************************************** }
{                                                                            }
{ BenchAdaptive                                                              }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

program BenchAdaptive;

{ A UNIFORM MESH AGAINST CURVATURE SAMPLING, at the same number of lines.

  The subject of the argument: a narrow peak, OFFSET so that it does not land
  on a node of the uniform mesh. Had it stood at the origin, the uniform mesh
  would have found it exactly - and the measurement would have proved the wrong
  thing.

  The true summit equals one. What is measured is how close each method comes
  to it AT AN EQUAL NUMBER OF SAMPLING LINES. That is the whole argument: not
  "whose picture is prettier" but who, with the same means, is nearer the
  truth. }

{$mode objfpc}{$H+}
{$APPTYPE CONSOLE}

uses
  SysUtils, DateUtils, Math, nsh_surface, nsh_adaptive;

const
  PEAK = 'exp(-400*((x-0.137)*(x-0.137) + (y+0.211)*(y+0.211)))';

var
  Xs, Ys : TDoubleArray;
  Z      : array of Double;
  E      : AnsiString;
  N, I   : LongInt;
  MaxU, MaxA : Double;
  T0: TDateTime;
  MsU, MsA: Double;

function GridMax(const Formula: AnsiString; const Ax, Ay: TDoubleArray): Double;
var
  K: LongInt;
  Err: AnsiString;
begin
  SetLength(Z, Length(Ax) * Length(Ay));
  if not EvalGrid(Formula, Ax, Ay, Z, Err) then
  begin
    Writeln('refused: ', Err);
    Halt(1);
  end;
  Result := -MaxDouble;
  for K := 0 to High(Z) do
    if (not IsNan(Z[K])) and (Z[K] > Result) then Result := Z[K];
end;

procedure UniformLines(out A: TDoubleArray; Lo, Hi: Double; Count: LongInt);
var
  K: LongInt;
begin
  SetLength(A, Count);
  for K := 0 to Count - 1 do A[K] := Lo + (Hi - Lo) * K / (Count - 1);
end;

begin
  Writeln('A NARROW PEAK, summit = 1.0, standing at (0.137, -0.211)');
  Writeln('');
  Writeln('  lines   miss uniform   miss adaptive   ms unif.   ms adapt.   times dearer');
  for I := 0 to 4 do
  begin
    N := 25 + I * 20;
    T0 := Now;
    UniformLines(Xs, -1, 1, N);
    UniformLines(Ys, -1, 1, N);
    MaxU := GridMax(PEAK, Xs, Ys);
    MsU := MilliSecondsBetween(Now, T0);
    T0 := Now;
    if not ChooseSamples(PEAK, -1, 1, -1, 1, N, Xs, Ys, E) then
    begin
      Writeln('  sampling refused: ', E);
      Halt(1);
    end;
    MaxA := GridMax(PEAK, Xs, Ys);
    MsA := MilliSecondsBetween(Now, T0);
    Writeln(Format('  %5d   %12.4f   %13.4f   %8.0f   %9.0f   %14.1f',
      [N, 1 - MaxU, 1 - MaxA, MsU, MsA, MsA / Max(MsU, 1)]));
  end;
end.
