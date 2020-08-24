# m h  dom mon dow   command
#0 * * * * /usr/bin/env bash projects.bash
log="$HOME/projects.log"
for project in "$HOME/Projects/"*
do
    git -C "$project" fetch --quiet --all --tags --prune
    remotes="$(git -C "$project" remote -v)"
    echo "$remotes" | grep -qw origin && echo "$project has an origin remote."
    heads="$(git -C "$project" show-ref --heads)"
    [ -z "$heads" ] || {
        echo "$project has one or more branches."
        echo "$heads" | sed 's/^/  /'
    }
    stashed="$(git -C "$project" stash list)"
    [ -z "$stashed" ] || {
        echo "$project has stashed changes."
        echo "$stashed" | sed 's/^/  /'
    }
    untracked="$(
        git -C "$project" ls-files \
            --directory \
            --exclude-standard \
            --no-empty-directory \
            --other \
    )"
    [ -z "$untracked" ] || {
        echo "$project has untracked changes."
        echo "$untracked" | sed 's/^/  /'
    }
done 1>"$log" 2>&1
[ -s "$log" ] || rm "$log"
