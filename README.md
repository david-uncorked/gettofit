# GetToFit!

GetToFit is a project cooked up at Uncorked Studios by Evans

### Reasons this exists
1. Evans has been an Up user for years. He has a 1st generation band that counts his steps really well, and he's become accustomed to it. 
2. Evans recently converted to using Android full time as he's been an Android developer for a few years.
3. Android has a great fitness product called Fit (<https://fit.google.com/>) that he also really likes.
4. Evans uses the elliptical every morning, and he wears his band, but not his phone so his step data wasn't getting accounted for in Google Fit.
4. After searching, he found that there was no clean way for him to get his Up step data into Fit.

## Solution
Use the great APIs provided by [Jawbone](https://jawbone.com/up/developer) and [Google](https://developers.google.com/fit/rest/) to resolve his step data from Up to Fit.

This repo is a first pass at the most basic operation needed to solve the problem. It authorizes Google's fitness API, then Jawbone's Up API, and registers a PubSub webhook so that every time a user syncs their Up band, a webhook is pinged with that data. The step data is then shuttled over to Google fit. 

## Reading Material

* [Uncorked Studios](http://www.uncorkedstudios.com)

* [GetToFit Blog Post](http://www.uncorkedstudios.com/) //to come

* [Uncorked Sudios Wearables Report](http://wearables.uncorkedstudios.com/)

* [GetToFit in the wild](https://utopian-outlook-92922.appspot.com)

## Roadmap
* ~~Workout Support~~ (In Testing as of 7/19/15)
* Better error handling
* Proper Google OAuth for AppEngine
* and/or less reliance on AppEngine