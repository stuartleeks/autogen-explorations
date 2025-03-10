# autogen explorations

This is a repo for personal explorations of autogen - it's not intended to be useful to anyone other than me. If you do find it useful, that's a nice bonus!

## random notes to sort


```bash
# install dependencies
poetry install


# TODO - add this to .bashrc?
eval $(poetry env activate)
```


```bash
# compile ts
(cd app_web/ts && tsc --watch)

# compile scss
cd app_web/scss
sass index.scss:../css/index.css # or sass --watch index.scss:../css/index.css
```

