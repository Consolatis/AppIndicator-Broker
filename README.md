A simple daemon able to create SNI tray icons.  
It listens to a named pipe and can be instructed to create or modify SNI entries.

Example flow:
```sh
export SNI_BROKER=/tmp/some_named_pipe

# Start the daemon and let it run in the background
./appindicator-broker.py "$SNI_BROKER" &

# Create a tray entry identified with "foo", using the vlc icon
echo "foo create vlc" > "$SNI_BROKER"

# Modify it
echo "foo title some title" > "$SNI_BROKER"
echo "foo label some <b>label</b>" > "$SNI_BROKER"
echo "foo hide" > "$SNI_BROKER"
echo "foo show" > "$SNI_BROKER"
echo "foo icon dialog-warning" > "$SNI_BROKER"

# Animate it
while true; do
	sleep 1;
	echo "foo icon vlc" > "$SNI_BROKER"
	sleep 1;
	echo "foo icon dialog-warning" > "$SNI_BROKER"
done

# Add a second tray entry, this time using the firefox icon
echo "bar create firefox" > "$SNI_BROKER"

# And clean up everything
kill %1
```

Issues:
- Unable to destroy the app indicator once it has been created without
  terminating the daemon. This might be caused by insufficient Python
  bindings as .unref() is not supported but the Python garbage collection
  doesn't handle this either after all references have been dropped.
