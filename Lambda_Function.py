from datetime import datetime, time
import boto3
import re

  theTag='Schedule'

  doLog = True

def EC2Scheduler(event, context):

  now = datetime.now().replace(second=0, microsecond=0)

  if doLog:
    print 'Reference time is ', now.time()

  ec2 = boto3.resource('ec2')

  allInstances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}])

  for instance in allInstances:
    if instance.tags :
      for tag in instance.tags:
        if tag['Key'] == theTag :
          Range=tag['Value']

          if doLog :
            print instance.instance_id, 

          shouldrun=shouldRunNow(instance, now, Range)

          if doLog :
            print 'should %s' %( 'run' if shouldrun else 'NOT run'),

          alignInstance(instance, shouldrun)

def shouldRunNow(instance, now, tRange):

  currentState = instance.state['Code'] == 16

  # is the tRange commented out

  if tRange[0:1] == '#':
    if doLog:
      print 'Range starts with # -- no changes',
    return currentState

  # does the time indicate an end-time only [eg -13:15]

  if tRange[0:1] == '-':
    tEnd=time(int(tRange[1:3]),int(tRange[4:6]))

    if doLog:
      print 'End time:', tEnd,

    if now.time() > tEnd:

      msg='stop'
      if tRange[6:7] == 'T':

        terminateAllowed=instance.describe_attribute(Attribute='disableApiTermination')['DisableApiTermination']['Value'] == False

        if terminateAllowed:
          instance.modify_attribute( Attribute='instanceInitiatedShutdownBehavior', Value='terminate' )
          msg='terminate'
        else:
          msg='stop [terminate not allowed]'

      # re-tag

      instance.delete_tags(Tags=[{'Key': theTag, 'Value': tRange}])
      instance.create_tags(Tags=[{'Key': theTag, 'Value': '#'+msg+'@'+tRange}])

      if doLog:
        print 'time to ', msg, 

      return False

    else:
      # leave instance in current state
      if doLog:
        print 'NO time to stop (yet) ',
      return currentState

  # some simple checks for tRange

  if not re.match('\d{2}:\d{2}-\d{2}:\d{2}',tRange):
    if doLog:
      print 'error in format of tag: >', tRange, '< -- no changes required ',

    instance.delete_tags(Tags=[{'Key': theTag}, {'Value': tRange}])
    instance.create_tags(Tags=[{'Key': theTag, 'Value': '# Err: '+tRange}])

    return currentState

  tStart=time(int(tRange[0:2]),int(tRange[3:5]))
  tEnd=time(int(tRange[6:8]),int(tRange[9:11]))

  inInterval = False
    
  # first case, start < end --> same day

  if tStart < tEnd:
    if tStart <= now.time() <= tEnd:        
      inInterval = True 

  # second case, end < start --> carry over to next day

  else:
    if tStart <= now.time() <= time(23,59) or time(0,0) <= now.time() <= tEnd:
      inInterval = True

  if doLog :
    print 'Ref time is %s interval' %( 'in' if inInterval else 'NOT in'), tRange, 

  return inInterval

def alignInstance(inst, requiredOn):

  actualOn = inst.state['Code'] == 16 
  msg='is compliant'

  if actualOn != requiredOn:
    if requiredOn == True:
      msg='starting'
      inst.start()
    else:
      termReq=inst.describe_attribute(Attribute='instanceInitiatedShutdownBehavior')['InstanceInitiatedShutdownBehavior']['Value'] == 'terminate'

      if termReq:
        msg='terminating'
        inst.terminate()
      else:
        msg='stopping'
        inst.stop()

  if doLog:
    print '-->', msg