{ ************************************************************************** }
{                                                                            }
{ BenchMesh                                                                  }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

program BenchMesh;

{ A MEASUREMENT BEFORE THE CHANGE. Without it there is nothing to prove the
  improvement from adaptive sampling with: "it got better" with no number is a
  feeling.

  Two different questions are measured, and the second matters more than the
  first:

  1. what building the mesh costs at each quality;
  2. WHETHER THE FORMULA IS COMPILED ONCE for the whole surface. The mesh is
     built row by row, and if the parser cache does not fire there will be as
     many compilations as there are rows - up to 256 instead of one. That
     assumption sits at the foundation of the whole design, and until now it
     had never been checked. }

{$mode objfpc}{$H+}
{$APPTYPE CONSOLE}

uses
  SysUtils, DateUtils, Math, Parser, ParseJit.Parser, nsh_surface;

var
  S: TSurface;
  E: AnsiString;
  Q, I: LongInt;
  T0: TDateTime;
  Ms: Double;

  { the same course as in BuildSurface, but with the counters in plain sight }
  procedure CountCompiles(const Formula: string; N: LongInt);
  var
    P: TJitParser;
    VX, VY: Double;
    Xs, Row: array of Double;
    J, K: LongInt;
  begin
    SetLength(Xs, N);
    SetLength(Row, N);
    for K := 0 to N - 1 do Xs[K] := -1 + 2 * K / (N - 1);
    P := TJitParser.Create(nil);
    try
      P.AddVariable('x', VX);
      P.AddVariable('y', VY);
      for J := 0 to N - 1 do
      begin
        VY := -1 + 2 * J / (N - 1);
        P.ExecuteMany(Formula, VX, Xs, Row);
      end;
      Writeln(Format('  rows %4d: compilations %3d, hits %6d, misses %4d',
        [N, P.CompileCount, P.HitCount, P.MissCount]));
    finally
      P.Free;
    end;
  end;

begin
  Writeln('COMPILATIONS PER SURFACE (expecting ONE, not one per row)');
  CountCompiles('sin(3*x) * cos(3*y)', 16);
  CountCompiles('sin(3*x) * cos(3*y)', 64);
  CountCompiles('sin(3*x) * cos(3*y)', 256);
  Writeln('');
  Writeln('BUILDING THE MESH, milliseconds per call');
  Writeln('   quality   side  verts       triangles   ms');
  for Q := 0 to 4 do
  begin
    I := Q * 25;
    T0 := Now;
    if not BuildSurface('sin(3*x) * cos(3*y)', -2, 2, -2, 2, I, S, E) then
    begin
      Writeln('  refused: ', E);
      Halt(1);
    end;
    Ms := MilliSecondsBetween(Now, T0);
    Writeln(Format('  %8d  %5d  %6d   %13d   %4.0f',
      [I, S.Side, Length(S.Verts), Length(S.Idx) div 3, Ms]));
  end;
  Writeln('');
  Writeln('THE SAME MESH AGAIN - is the parser cache visible between calls');
  for I := 1 to 3 do
  begin
    T0 := Now;
    BuildSurface('sin(3*x) * cos(3*y)', -2, 2, -2, 2, 100, S, E);
    Writeln(Format('  pass %d: %4.0f ms', [I, MilliSecondsBetween(Now, T0) * 1.0]));
  end;
end.
