{ ************************************************************************** }
{                                                                            }
{ MeshProbe                                                                  }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

program MeshProbe;

{ A mesh probe WITHOUT graphics: what is checked is the thing the library was
  started for - that the value at a node equals the value of the formula, and
  that a hole appears where a number stops being a number. }

{$mode objfpc}{$H+}
{$APPTYPE CONSOLE}

uses
  SysUtils, Math, nsh_surface, nsh_adaptive;

var
  C0, H0, M0, C1, H1, M1: Int64;
  AX, AY: TDoubleArray;
  Near, Far_: LongInt;
  K2: LongInt;

var
  Ok  : LongInt = 0;
  Bad : LongInt = 0;

procedure Check(const Name: string; Cond: Boolean; const Got: string);
begin
  if Cond then
  begin
    Inc(Ok);
    Writeln('  ok   ', Name:52, '  ', Got);
  end
  else begin
    Inc(Bad);
    Writeln('  FAIL ', Name:52, '  ', Got);
  end;
end;

var
  S     : TSurface;
  E     : AnsiString;
  N, K  : LongInt;
  Want  : Double;
begin
  Writeln('MESH FROM FORMULA');
  Check('quality 0 gives 16 nodes', SideFromQuality(0) = 16, IntToStr(SideFromQuality(0)));
  Check('quality 100 gives 256', SideFromQuality(100) = 256, IntToStr(SideFromQuality(100)));

  { z = x*x + y*y on [-1,1] is a smooth bowl: there must be no holes }
  Check('bowl built', BuildSurface('x*x + y*y', -1, 1, -1, 1, 0, S, E), 'error: ' + E);
  N := S.Side;
  Check('nodes per side 16', N = 16, IntToStr(N));
  Check('vertices N*N', Length(S.Verts) = N * N, IntToStr(Length(S.Verts)));
  Check('indices for every cell', Length(S.Idx) = (N - 1) * (N - 1) * 6, IntToStr(Length(S.Idx)));
  Check('no holes', S.Holes = 0, IntToStr(S.Holes));
  { The bottom of the bowl lies BETWEEN the nodes: with 16 nodes over [-1,1]
    the step is 2/15, and zero does not land on a node. So the minimum of the
    mesh is 0.00889 rather than 0 - and that is NOT a defect but exactly the
    trouble that curvature sampling with exact placement of special points is
    being built for in 1.1. This check pins down today's behaviour so that
    tomorrow's improvement shows up as a number. }
  Check('bowl minimum is the GRID minimum, not the true one',
        (S.ZMin > 0) and (S.ZMin < 0.01), FloatToStrF(S.ZMin, ffFixed, 8, 6));
  Check('bowl maximum 2', Abs(S.ZMax - 2) < 1E-9, FloatToStrF(S.ZMax, ffFixed, 8, 6));

  { the value at a given node has to equal the formula at its own coordinates }
  K := 5 * N + 3;
  Want := S.Verts[K].X * S.Verts[K].X + S.Verts[K].Y * S.Verts[K].Y;
  Check('node equals the formula at its own point',
        Abs(S.Verts[K].Z - Want) < 1E-5,
        FloatToStrF(S.Verts[K].Z, ffFixed, 8, 6) + ' vs ' + FloatToStrF(Want, ffFixed, 8, 6));

  { the normal has to be of unit length }
  Check('normal is unit length',
    Abs(Sqrt(Sqr(S.Verts[K].NX) + Sqr(S.Verts[K].NY) + Sqr(S.Verts[K].NZ)) - 1) < 1E-5,
    FloatToStrF(Sqrt(Sqr(S.Verts[K].NX) + Sqr(S.Verts[K].NY) + Sqr(S.Verts[K].NZ)), ffFixed, 8, 6));

  { a plane: the span is zero, but the surface is legitimate }
  Check('flat plane builds', BuildSurface('1', -1, 1, -1, 1, 0, S, E), E);
  Check('flat plane has no holes', S.Holes = 0, IntToStr(S.Holes));

  { 1/x over a domain that includes zero: holes MUST appear }
  { The domain [-1,2] is deliberate: with 16 nodes the step is 0.2, and zero
    DOES land on a node. On [-1,1] it is not in the mesh at all, no infinity
    arises and there will be no holes - the mesh walks past the singularity. }
  Check('1/x builds', BuildSurface('1/x', -1, 2, -1, 1, 0, S, E), E);
  Check('and it has holes where x hits zero', S.Holes > 0, IntToStr(S.Holes));
  Check('and is not all holes', Length(S.Idx) > 0, IntToStr(Length(S.Idx)));

  { an empty formula and an inverted domain have to BE REFUSED }
  Check('empty formula refused', not BuildSurface('', -1, 1, -1, 1, 0, S, E), E);
  Check('inverted domain refused', not BuildSurface('x', 1, -1, -1, 1, 0, S, E), E);
  Check('nonsense refused', not BuildSurface('x +* ', -1, 1, -1, 1, 0, S, E), E);
  { COMPILATION ONCE, AND ACROSS CALLS. This is the reason for the threefold
    speed-up, and without a check it will be undone in silence: it takes one
    person creating a parser inside BuildSurface again. Two cases: the same
    formula does NOT move the counter, a different one does. A check with only
    the first case is green even when no compilation happens at all. }
  Writeln('COMPILATION IS PAID ONCE');
  BuildSurface('sin(3*x) + y', -1, 1, -1, 1, 0, S, E);
  EngineStats(C0, H0, M0);
  BuildSurface('sin(3*x) + y', -1, 1, -1, 1, 20, S, E);
  BuildSurface('sin(3*x) + y', -1, 1, -1, 1, 40, S, E);
  EngineStats(C1, H1, M1);
  Check('same formula compiles no more', C1 = C0, IntToStr(C0) + ' -> ' + IntToStr(C1));
  Check('but it IS being evaluated', H1 > H0, IntToStr(H1 - H0) + ' more hits');
  BuildSurface('cos(5*x) - y', -1, 1, -1, 1, 20, S, E);
  EngineStats(C1, H1, M1);
  Check('a different formula does compile', C1 > C0, IntToStr(C0) + ' -> ' + IntToStr(C1));
  { CURVATURE SAMPLING. Two cases, and the second matters more: on a plane
    there is nothing to refine, and an algorithm that refines ALWAYS is green
    on the peak and worthless as evidence. }
  Writeln('CURVATURE SAMPLING');
  Check(
    'peak: lines chosen',
    ChooseSamples(
      'exp(-40*((x-0.137)*(x-0.137) + y*y))',
      -1,
      1,
      -1,
      1,
      49,
      AX,
      AY,
      E
    ),
    E
  );
  Check('budget respected', Length(AX) <= 49, IntToStr(Length(AX)));
  Check('ends are the domain ends',
        (Abs(AX[0] + 1) < 1E-12) and (Abs(AX[High(AX)] - 1) < 1E-12), 'ok');
  Check('sorted, no duplicates', True, 'checked below');
  for K2 := 1 to High(AX) do
    if AX[K2] <= AX[K2 - 1] then
    begin
      Check('sorted, no duplicates', False, 'at ' + IntToStr(K2));
      Break;
    end;

  { the extra nodes stand by the peak rather than being spread out evenly }
  Near := 0;
  Far_ := 0;
  for K2 := 0 to High(AX) do
    if Abs(AX[K2] - 0.137) < 0.25 then
      Inc(Near)
    else
      Inc(Far_);
  Check('lines cluster AT the peak', Near > Length(AX) div 4,
        IntToStr(Near) + ' near vs ' + IntToStr(Far_) + ' far');

  { A PLANE: there is nothing to split, and no extra lines should appear }
  Check('flat: lines chosen', ChooseSamples('1', -1, 1, -1, 1, 49, AX, AY, E), E);
  Check('flat surface is NOT refined', Length(AX) = 17, IntToStr(Length(AX)));

  { A SLOPE does not bend either - the second difference is zero }
  Check('slope: lines chosen', ChooseSamples('x + y', -1, 1, -1, 1, 49, AX, AY, E), E);
  Check('a plane is NOT refined either', Length(AX) = 17, IntToStr(Length(AX)));
  Writeln('');
  Writeln('checks: ', Ok + Bad, ', failed: ', Bad);
  if Bad > 0 then Halt(1);
end.
