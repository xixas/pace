#!/bin/bash
# Assemble Pace design draft 2 from draft-1 head + plan sections + mockup fragments.
set -e
S=/home/vikas/work/osmosys/pace/docs/src
OUT=/home/vikas/work/osmosys/pace/docs/design.html
{
  sed -n 1,88p /home/vikas/work/osmosys/pace/docs/design-draft1.html
  cat $S/plan-top.html
  echo '<h3 class="text-xl font-bold pt-4 border-t border-base-300">A · Getting started and account</h3>'
  cat $S/frag-a.html
  echo '<h3 class="text-xl font-bold pt-4 border-t border-base-300">B · Always visible: panel, tray, widget</h3>'
  cat $S/frag-b.html
  echo '<h3 class="text-xl font-bold pt-4 border-t border-base-300">C · Dashboard, notifications, settings, leads, lifecycle</h3>'
  cat $S/frag-c.html
  cat $S/plan-bottom.html
  echo '</body></html>'
} > $OUT.tmp
mv $OUT.tmp $OUT
wc -c $OUT
