#!/bin/bash

echo -n "Feeding NLRI data to goBGPd..."
lineno=0
while IFS= read -r line
do
  lineno=$((lineno + 1))
  gobgp global rib add -a $line
  if [ $? -ne 0 ]
  then
    echo "ERROR: line($lineno): $line"
  fi
done
echo "Done"

