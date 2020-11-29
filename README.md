# Metagit

Git for Git Repositories

******

If you:
- have a directory full of Git repos
- want to version-control the configuration of those repos
- like Git

Then you might find Metagit useful. It offers a Git-like experience for managing Git repos.

## Demo

Initialize a Metagit repository:
```
$ cd ~/projects/    # or wherever you store your Git projects, or use metagit -C
$ metagit init      # creates .metagit, a Git repo where tracked project configs are kept
Initialized Metagit repository in /home/dmtucker/projects
$ metagit status
Untracked projects
  (use "metagit add <project>..." to begin tracking)
	project1/
	project2/

```
Track changes to project config:
```
$ metagit add project1/ project2/    # start tracking some projects
$ git -C project1/ remote add foo git@somehost.com:foo/project1.git
$ rm -rf project2/
$ metagit status
Changes
  (use "metagit add/rm <project>..." to accept changes)
  (use "metagit restore <project>..." to undo changes)
	modified: project1
	deleted:  project2

```
Git tracks lines in files. Metagit tracks config in projects.
``` diff
$ metagit diff
diff --git a/project1 b/project1
index 515f483..93a874c 100644
--- a/project1
+++ b/project1
@@ -3,3 +3,6 @@
 	filemode = true
 	bare = false
 	logallrefupdates = true
+[remote "foo"]
+	url = git@somehost.com:foo/project1.git
+	fetch = +refs/heads/*:refs/remotes/foo/*
diff --git a/project2 b/project2
deleted file mode 100644
index 515f483..0000000
--- a/project2
+++ /dev/null
@@ -1,5 +0,0 @@
-[core]
-	repositoryformatversion = 0
-	filemode = true
-	bare = false
-	logallrefupdates = true
```
This example deleted `project2` so as to demonstrate `metagit restore` (below), but keep in mind, *ONLY CONFIGURATION IS TRACKED*.
If you need all of `project2` back, you should restore from a backup.
``` sh 
$ metagit restore project2  # only restores git config! not branches/tags/etc.
$ metagit add project1      # add the project again to keep the changes
$ metagit rm project1       # stop tracking a project (does not affect the actual project)
```

## About `.metagit`

`.metagit` is just another Git repo in your projects folder. It is created by `metagit init`, which automatically starts tracking it.
When `metagit add` is used to start tracking a project, that project's `.git/config` file is copied into `.metagit` and committed.
```
$ git -C .metagit log
36cec91 (HEAD -> master) Remove project1
a1ed312 Add project1
185ed15 Add project2
e4d274d Add project1
1e16b5e Add .metagit
```
Pro tip: Consider a clone of the `.metagit` repo a (Metagit) "clone" of your projects folder.
For example, push the `.metagit` repo to GitHub to allow for easy provisioning of new dev machines:
``` sh
$ mkdir ~/projects
$ cd ~/projects/
$ git clone git@github.com:dmtucker/.metagit.git
...
$ metagit restore project2
```
