#!/usr/bin/env bash
# Synchronisation manuelle : relance la recuperation et rafraichit les boites.
# Usage :  sync.sh [digest|recos|events|all]     (defaut : all)
EWW="$HOME/.cargo/bin/eww"
CFG="$HOME/.config/eww"
what="${1:-all}"

case "$what" in
  digest|all) "$EWW" update digest="$(bash "$CFG/fetch-digest.sh")" ;;
esac
case "$what" in
  recos|all)  "$EWW" update recos="$(bash "$CFG/fetch-recos.sh")" ;;
esac
case "$what" in
  events|all) "$EWW" update events="$(bash "$CFG/fetch-events.sh")" ;;
esac
