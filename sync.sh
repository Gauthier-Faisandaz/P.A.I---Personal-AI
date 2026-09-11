#!/usr/bin/env bash
# Synchronisation manuelle : relance la recuperation et rafraichit les boites.
# Usage :  sync.sh [digest|recos|venir|veille|all]      (defaut : all)
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
  venir|all)  "$EWW" update venir="$(bash "$CFG/fetch-venir.sh")" ;;
esac
case "$what" in
  veille|all) "$EWW" update veille="$(bash "$CFG/fetch-veille.sh")" ;;
esac
