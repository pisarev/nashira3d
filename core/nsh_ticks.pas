{ ************************************************************************** }
{                                                                            }
{ nsh_ticks                                                                  }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

unit nsh_ticks;

{$mode objfpc}{$H+}

interface

function NiceStep(V: Double): Double;

function StepUp(V: Double): Double;

implementation

uses
  Math;

function NiceStep(V: Double): Double;
var
  E, Best, Cand, BestD: Double;
  K, J: LongInt;
const
  M: array[0..2] of Double = (1, 2, 5);
begin
  if V <= 0 then Exit(1);
  E := Floor(Log10(V));
  Best := 1;
  BestD := 1E30;
  for K := -1 to 1 do
    for J := 0 to 2 do
    begin
      Cand := M[J] * Power(10, E + K);
      if Cand <= 0 then Continue;
      if Abs(Ln(Cand) - Ln(V)) < BestD then
      begin
        BestD := Abs(Ln(Cand) - Ln(V));
        Best := Cand;
      end;
    end;
  Result := Best;
end;

function StepUp(V: Double): Double;
var E, M: Double;
begin
  if V <= 0 then Exit(1);
  E := Power(10, Floor(Log10(V)));
  M := V / E;
  if M < 1.5 then
    Result := 2 * E
  else if M < 3.5 then
    Result := 5 * E
  else
    Result := 10 * E;
end;

end.
